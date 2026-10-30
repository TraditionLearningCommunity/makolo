import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:video_player/video_player.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../platform/media/private_media_views.dart';
import '../../platform/sharing/share_gateway.dart';
import 'discovery_offline_store.dart';
import 'discovery_save_icon.dart';

/// A transient reader for already-authorized Discovery presentation destinations.
/// This is not a permission grant or a replacement for the server-side checks.
class DiscoveryReaderItem {
  const DiscoveryReaderItem({
    required this.title,
    required this.uri,
    required this.mimeType,
    this.inlineText,
    this.authorizedImageBytes,
  });

  final String title;
  final Uri uri;
  final String mimeType;
  /// Authenticated loader for published recognition media. This is called
  /// through the owner-gated Makolo API, never an unauthenticated HTTP client.
  /// Only publicly published recognition images may use offline retention.
  final Future<Uint8List> Function()? authorizedImageBytes;
  /// Public text already carried by a permitted owner projection.
  /// It is not fetched again and does not create a new document identity.
  final String? inlineText;
}

bool discoverySafeDestination(Uri? uri) =>
    uri != null &&
    (uri.scheme == 'http' || uri.scheme == 'https') &&
    uri.host.isNotEmpty &&
    uri.userInfo.isEmpty;

class DiscoveryReader extends StatefulWidget {
  const DiscoveryReader({
    super.key,
    required this.items,
    this.initialIndex = 0,
    this.sharing = const SystemShareGateway(),
  });

  final List<DiscoveryReaderItem> items;
  final int initialIndex;
  final ShareGateway sharing;

  @override
  State<DiscoveryReader> createState() => _DiscoveryReaderState();
}

class _DiscoveryReaderState extends State<DiscoveryReader> {
  late int _index;
  late final PageController _page;
  File? _temporaryFile;
  VideoPlayerController? _player;
  String? _text;
  Uint8List? _imageBytes;
  String? _failure;
  bool _loading = false;
  bool _exporting = false;
  bool _offlineBusy = false;
  bool _offlineSaved = false;
  File? _retainedFile;
  final DiscoveryOfflineStore _offlineStore = const DiscoveryOfflineStore();
  int _generation = 0;

  DiscoveryReaderItem get _item => widget.items[_index];

  @override
  void initState() {
    super.initState();
    _index = widget.initialIndex.clamp(0, widget.items.length - 1).toInt();
    _page = PageController(initialPage: _index);
    _load();
  }

  Future<void> _disposeLoaded() async {
    final player = _player;
    _player = null;
    await player?.dispose();
    final previous = _temporaryFile;
    _temporaryFile = null;
    if (previous != null) {
      try {
        if (await previous.exists()) await previous.delete();
      } on FileSystemException {
        // The OS may still hold a transient viewer handle.
      }
    }
  }

  Future<File> _fetchTemporary(DiscoveryReaderItem item) async {
    // Published recognition media must use its authenticated API transport.
    // The bytes are never downloaded directly from the media URL.
    if (item.authorizedImageBytes != null) {
      final data = await item.authorizedImageBytes!();
      if (data.isEmpty || data.length > 8 * 1024 * 1024) {
        throw const FormatException('Image indisponible');
      }
      final dir = await getTemporaryDirectory();
      final ext = item.mimeType.toLowerCase() == 'image/jpeg' ? 'jpg' : 'png';
      final file = File(
        '${dir.path}/makolo-discovery-${DateTime.now().microsecondsSinceEpoch}.$ext',
      );
      await file.writeAsBytes(data, flush: true);
      return file;
    }
    // Downloads are triggered only on opening a document or exporting it.
    // Never follow a redirect to another origin or an untrusted scheme.
    if (!discoverySafeDestination(item.uri)) {
      throw const FormatException('Destination non autorisée');
    }
    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 15);
    File? output;
    try {
      final request = await client.getUrl(item.uri);
      request.followRedirects = false;
      final response = await request.close();
      if (response.statusCode != HttpStatus.ok) {
        throw HttpException('HTTP ${response.statusCode}');
      }
      final expectedType = item.mimeType.toLowerCase();
      final actualType = response.headers.contentType?.mimeType.toLowerCase();
      if (actualType != null &&
          expectedType != 'application/octet-stream' &&
          expectedType != actualType) {
        throw const FormatException('Type de fichier inattendu');
      }
      const maxBytes = 20 * 1024 * 1024;
      if (response.contentLength > maxBytes) {
        throw const FormatException('Fichier trop volumineux');
      }
      final dir = await getTemporaryDirectory();
      final ext = switch (item.mimeType.toLowerCase()) {
        'application/pdf' => 'pdf',
        'text/csv' => 'csv',
        'text/plain' => 'txt',
        'image/png' => 'png',
        'image/jpeg' => 'jpg',
        'video/mp4' => 'mp4',
        'audio/mpeg' => 'mp3',
        'audio/wav' => 'wav',
        _ => 'bin',
      };
      output = File(
        '${dir.path}/makolo-discovery-${DateTime.now().microsecondsSinceEpoch}.$ext',
      );
      final sink = output.openWrite();
      var received = 0;
      try {
        await for (final chunk in response) {
          received += chunk.length;
          if (received > maxBytes) {
            throw const FormatException('Fichier trop volumineux');
          }
          sink.add(chunk);
        }
      } finally {
        await sink.close();
      }
      return output;
    } on Object {
      if (output != null && await output.exists()) await output.delete();
      rethrow;
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _load() async {
    final generation = ++_generation;
    await _disposeLoaded();
    if (!mounted || generation != _generation) return;
    setState(() {
      _loading = false;
      _failure = null;
      _text = null;
      _imageBytes = null;
    });
    final item = _item;
    final type = item.mimeType.toLowerCase();
    if (type == 'text/plain' && item.inlineText != null) {
      setState(() => _text = item.inlineText);
      return;
    }
    File? cached;
    if (type != 'text/html') {
      try {
        cached = await _offlineStore.retained(item.uri);
      } on Object {
        // Path provider may be unavailable in tests or restricted environments.
        cached = null;
      }
    }
    if (!mounted || generation != _generation) return;
    _retainedFile = cached;
    _offlineSaved = cached != null;
    if (type.startsWith('image/')) {
      if (cached != null || item.authorizedImageBytes == null) {
        setState(() {});
        return;
      }
      setState(() => _loading = true);
      try {
        final bytes = await item.authorizedImageBytes!();
        if (!mounted || generation != _generation) return;
        if (bytes.isEmpty || bytes.length > 8 * 1024 * 1024) {
          throw const FormatException('Image indisponible');
        }
        setState(() => _imageBytes = bytes);
      } on Object {
        if (mounted && generation == _generation) {
          setState(() => _failure =
              'Lecture indisponible. Vérifiez la connexion et les droits.');
        }
      } finally {
        if (mounted && generation == _generation) {
          setState(() => _loading = false);
        }
      }
      return;
    }
    if (type != 'application/pdf' &&
        type != 'text/plain' &&
        type != 'text/csv' &&
        !type.startsWith('video/') &&
        !type.startsWith('audio/')) {
      return;
    }
    setState(() => _loading = true);
    try {
      if (type.startsWith('video/') || type.startsWith('audio/')) {
        final player = cached != null
            ? VideoPlayerController.file(cached)
            : VideoPlayerController.networkUrl(item.uri);
        await player.initialize();
        if (!mounted || generation != _generation) {
          await player.dispose();
          return;
        }
        setState(() => _player = player);
      } else {
        final file = cached ?? await _fetchTemporary(item);
        if (!mounted || generation != _generation) {
          if (cached == null) await file.delete();
          return;
        }
        if (type == 'text/plain' || type == 'text/csv') {
          final text = await file.readAsString(encoding: utf8);
          if (!mounted || generation != _generation) {
            if (cached == null) await file.delete();
            return;
          }
          setState(() => _text = text);
        }
        if (cached == null) _temporaryFile = file;
      }
    } on Object {
      if (mounted && generation == _generation) {
        setState(
          () => _failure =
              'Lecture indisponible. Vérifiez la connexion et les droits.',
        );
      }
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _export() async {
    if (_exporting) return;
    setState(() => _exporting = true);
    File? generated;
    try {
      final item = _item;
      // A Web page is not silently treated as a downloadable file.
      if (item.mimeType == 'text/html') return;
      final file = _temporaryFile;
      if (item.inlineText != null) {
        final dir = await getTemporaryDirectory();
        generated = File(
          '${dir.path}/makolo-resource-${DateTime.now().microsecondsSinceEpoch}.txt',
        );
        await generated.writeAsString(item.inlineText!, encoding: utf8);
      } else {
        generated = file ?? _retainedFile ?? await _fetchTemporary(item);
      }
      await widget.sharing.shareFiles(paths: [generated.path]);
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Export impossible. Vérifiez la connexion et les droits.',
            ),
          ),
        );
      }
    } finally {
      if (generated != null &&
          generated != _temporaryFile &&
          generated != _retainedFile) {
        try {
          if (await generated.exists()) await generated.delete();
        } on FileSystemException {
          // The receiving OS app may keep the handle temporarily.
        }
      }
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _toggleOffline() async {
    if (_offlineBusy || _item.mimeType == 'text/html' ||
        _item.inlineText != null) return;
    final item = _item;
    final generation = _generation;
    setState(() => _offlineBusy = true);
    File? temporary;
    try {
      if (_offlineSaved) {
        await _offlineStore.remove(item.uri);
        if (!mounted || generation != _generation) return;
        _retainedFile = null;
        _offlineSaved = false;
        await _load();
      } else {
        final file = _temporaryFile ?? await _fetchTemporary(item);
        if (file != _temporaryFile) temporary = file;
        final retained = await _offlineStore.save(item.uri, file);
        if (!mounted || generation != _generation) return;
        _retainedFile = retained;
        setState(() => _offlineSaved = true);
      }
    } on Object {
      if (mounted && generation == _generation) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Impossible de modifier la copie hors ligne.'),
          ),
        );
      }
    } finally {
      if (temporary != null) {
        try {
          if (await temporary.exists()) await temporary.delete();
        } on FileSystemException {
          // Transient download cleanup.
        }
      }
      if (mounted && generation == _generation) {
        setState(() => _offlineBusy = false);
      }
    }
  }

  Future<void> _shareLink() async {
    final item = _item;
    if (item.authorizedImageBytes != null) {
      File? generated;
      try {
        generated = _retainedFile ?? _temporaryFile ?? await _fetchTemporary(item);
        await widget.sharing.shareFiles(paths: [generated.path]);
      } on Object {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Le partage n’a pas pu aboutir.')),
          );
        }
      } finally {
        if (generated != null &&
            generated != _retainedFile && generated != _temporaryFile) {
          try {
            if (await generated.exists()) await generated.delete();
          } on FileSystemException {
            // The receiving application may hold its temporary share.
          }
        }
      }
      return;
    }
    if (item.inlineText == null && !discoverySafeDestination(item.uri)) return;
    try {
      final shared = item.inlineText == null
          ? '${item.title}\n${item.uri}'
          : '${item.title}\n${item.inlineText}';
      await widget.sharing.shareText(shared);
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Le partage n’a pas pu aboutir.')),
        );
      }
    }
  }

  Future<void> _copyLink() async {
    final uri = _item.uri;
    if (_item.inlineText == null && !discoverySafeDestination(uri)) return;
    try {
      await Clipboard.setData(ClipboardData(
        text: _item.inlineText ?? uri.toString(),
      ));
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Copié.')));
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de copier le lien.')),
        );
      }
    }
  }

  Future<void> _openWebsite() async {
    final uri = _item.uri;
    if (!discoverySafeDestination(uri)) return;
    try {
      final opened = await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
      if (!opened && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Cette page ne peut pas être ouverte ici.'),
          ),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Cette page ne peut pas être ouverte ici.'),
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    _generation++;
    _page.dispose();
    // Dispose native media and ephemeral bytes without blocking navigation.
    _disposeLoaded();
    super.dispose();
  }

  Widget _content() {
    if (_failure != null) return Center(child: Text(_failure!));
    if (_loading) return const Center(child: CircularProgressIndicator());
    final item = _item;
    final type = item.mimeType.toLowerCase();
    if (type.startsWith('image/')) {
      return InteractiveViewer(
        minScale: 0.7,
        maxScale: 6,
        child: Center(
          child: _retainedFile != null
              ? Image.file(
                  _retainedFile!,
                  fit: BoxFit.contain,
                  semanticLabel: item.title,
                )
              : _imageBytes != null
              ? Image.memory(
                  _imageBytes!,
                  fit: BoxFit.contain,
                  semanticLabel: item.title,
                  errorBuilder: (_, _, _) => const Text('Image indisponible.'),
                )
              : Image.network(
                  item.uri.toString(),
                  fit: BoxFit.contain,
                  semanticLabel: item.title,
                  errorBuilder: (_, _, _) => const Text('Image indisponible.'),
                ),
        ),
      );
    }
    if (type == 'application/pdf' &&
        (_temporaryFile != null || _retainedFile != null)) {
      return PrivatePdfView(path: (_temporaryFile ?? _retainedFile)!.path);
    }
    if ((type == 'text/plain' || type == 'text/csv') && _text != null) {
      return SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: SelectableText(_text!),
      );
    }
    if ((type.startsWith('video/') || type.startsWith('audio/')) &&
        _player != null) {
      final player = _player!;
      return Center(
        child: ValueListenableBuilder<VideoPlayerValue>(
          valueListenable: player,
          builder: (context, value, _) => Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (type.startsWith('video/'))
                AspectRatio(
                  aspectRatio: value.aspectRatio > 0
                      ? value.aspectRatio
                      : 16 / 9,
                  child: VideoPlayer(player),
                )
              else
                const Icon(Icons.audiotrack, size: 64),
              IconButton.filledTonal(
                tooltip: value.isPlaying ? 'Pause' : 'Lire',
                onPressed: () =>
                    value.isPlaying ? player.pause() : player.play(),
                icon: Icon(value.isPlaying ? Icons.pause : Icons.play_arrow),
              ),
              Slider(
                value: value.duration.inMilliseconds > 0
                    ? value.position.inMilliseconds
                          .toDouble()
                          .clamp(0.0, value.duration.inMilliseconds.toDouble())
                          .toDouble()
                    : 0,
                max: value.duration.inMilliseconds > 0
                    ? value.duration.inMilliseconds.toDouble()
                    : 1,
                onChanged: (position) =>
                    player.seekTo(Duration(milliseconds: position.round())),
              ),
            ],
          ),
        ),
      );
    }
    if (type == 'text/html') {
      return Center(
        child: TextButton.icon(
          onPressed: _openWebsite,
          icon: const Icon(Icons.open_in_browser),
          label: const Text('Consulter dans Makolo'),
        ),
      );
    }
    return const Center(
      child: Text(
        'Ce format ne possède pas encore de lecteur natif. Utilisez l’export.',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final item = _item;
    final website = item.mimeType == 'text/html';
    return Scaffold(
      appBar: AppBar(
        title: Text(item.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        actions: [
          if (!website && item.inlineText == null)
            IconButton(
              tooltip: _offlineSaved
                  ? 'Supprimer la copie hors ligne Makolo'
                  : 'Garder hors ligne dans Makolo',
              onPressed: _offlineBusy ? null : _toggleOffline,
              icon: DiscoveryOrbitIcon(
                saved: _offlineSaved,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
          if (!website)
            IconButton(
              tooltip: 'Exporter vers l’appareil',
              onPressed: _exporting ? null : _export,
              icon: const Icon(Icons.download_outlined),
            ),
          if (!website)
            PopupMenuButton<String>(
              tooltip: 'Partager cette ressource',
              icon: const Icon(Icons.share_outlined),
              onSelected: (action) {
                if (action == 'copy') {
                  _copyLink();
                } else if (action == 'share') {
                  _shareLink();
                }
              },
              itemBuilder: (_) => [
                if (item.authorizedImageBytes == null)
                  const PopupMenuItem(
                    value: 'copy',
                    child: ListTile(
                      leading: Icon(Icons.copy_outlined),
                      title: Text('Copier le lien'),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                const PopupMenuItem(
                  value: 'share',
                  child: ListTile(
                    leading: Icon(Icons.share_outlined),
                    title: Text('Partager avec…'),
                    contentPadding: EdgeInsets.zero,
                  ),
              ],
            ),
          if (website)
            IconButton(
              tooltip: 'Ouvrir la page',
              onPressed: _openWebsite,
              icon: const Icon(Icons.open_in_browser),
            ),
        ],
      ),
      body: SafeArea(
        child: widget.items.length == 1
            ? _content()
            : Column(
                children: [
                  Expanded(
                    child: PageView.builder(
                      controller: _page,
                      itemCount: widget.items.length,
                      onPageChanged: (index) {
                        setState(() => _index = index);
                        _load();
                      },
                      itemBuilder: (context, index) => index == _index
                          ? _content()
                          : const SizedBox.shrink(),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.all(8),
                    child: Text('${_index + 1} / ${widget.items.length}'),
                  ),
                ],
              ),
      ),
    );
  }
}
