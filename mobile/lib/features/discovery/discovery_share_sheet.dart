import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:pretty_qr_code/pretty_qr_code.dart';

import '../../network/makolo_api_client.dart';
import '../../platform/sharing/share_gateway.dart';
import 'discovery_selector.dart';

/// Reuses the canonical Sharing owner API; no local envelope or fake delivery.
class DiscoveryShareControl extends StatefulWidget {
  const DiscoveryShareControl({
    super.key,
    required this.item,
    required this.api,
    required this.authenticated,
    this.onSignIn,
    this.iconOnly = false,
    this.baseUri,
  });

  final DiscoveryItemPresentation item;
  final MakoloApiClient? api;
  final bool authenticated;
  final VoidCallback? onSignIn;
  final bool iconOnly;
  final Uri? baseUri;

  @override
  State<DiscoveryShareControl> createState() => _DiscoveryShareControlState();
}

class _DiscoveryShareControlState extends State<DiscoveryShareControl> {
  bool _busy = false;
  Map<String, dynamic>? _created;

  String get _endpoint =>
      'api/v1/sharing/possibilities/'
      '${Uri.encodeComponent(widget.item.family)}/'
      '${Uri.encodeComponent(widget.item.id)}/';

  Uri? get _shareUrl {
    final text = _created?['url'];
    if (text is! String) return null;
    final uri = Uri.tryParse(text);
    return uri != null && uri.scheme == 'https' && uri.host.isNotEmpty
        ? uri
        : null;
  }

  // The public item URL is projected by Discovery from its canonical Web
  // presentation. It contains no sender identity, session or private delivery.
  Uri? get _publicItemUrl {
    final raw = widget.item.links['web'];
    if (raw == null || raw.isEmpty) return null;
    final parsed = Uri.tryParse(raw);
    if (parsed == null) return null;
    final resolved = parsed.hasScheme
        ? parsed
        : widget.baseUri?.resolveUri(parsed);
    if (resolved == null ||
        (resolved.scheme != 'https' && resolved.scheme != 'http') ||
        resolved.host.isEmpty ||
        resolved.userInfo.isNotEmpty) {
      return null;
    }
    return resolved;
  }

  void _feedback(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _action(Future<void> Function() task) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await task();
    } on Object {
      _feedback('Le partage n’a pas pu aboutir. Réessayez.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<Uri> _link() async {
    if (_shareUrl != null) return _shareUrl!;
    final api = widget.api;
    if (api == null ||
        !widget.authenticated ||
        widget.item.links['web_share'] == null) {
      final publicUrl = _publicItemUrl;
      if (publicUrl == null) throw StateError('Public share URL unavailable');
      return publicUrl;
    }
    final result = await api.post(_endpoint, body: {'intent': 'view'});
    final data = result.jsonObject();
    if (data['state'] != 'link') {
      throw const FormatException('Unexpected share contract');
    }
    setState(() => _created = data);
    final url = _shareUrl;
    if (url == null) throw const FormatException('Invalid share URL');
    return url;
  }

  Future<void> _external() => _action(() async {
    final url = await _link();
    await const SystemShareGateway().shareText('${widget.item.title}\n$url');
  });

  Future<void> _copy() => _action(() async {
    final url = await _link();
    await Clipboard.setData(ClipboardData(text: url.toString()));
    _feedback('Lien copié.');
  });

  Future<void> _qr() => _action(() async {
    final url = await _link();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('QR de partage'),
        content: SizedBox(
          width: 220,
          height: 220,
          child: PrettyQrView.data(data: url.toString()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Fermer'),
          ),
        ],
      ),
    );
  });

  Future<void> _internal() async {
    if (_busy) return;
    final api = widget.api;
    if (api == null || !widget.authenticated) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => _ShareRecipientPicker(
        api: api,
        endpoint: _endpoint,
        onDelivered: () => _feedback('Partage envoyé dans Makolo.'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // The owner Web share reference is the current contract for shareability.
    // Presence of a public card alone never grants sharing authority.
    if (widget.item.links['web'] == null &&
        widget.item.links['web_share'] == null) {
      return widget.iconOnly
          ? const IconButton(
              onPressed: null,
              tooltip: 'Partager',
              icon: Icon(Icons.share_outlined),
            )
          : TextButton.icon(
              onPressed: null,
              icon: const Icon(Icons.share_outlined),
              label: const Text('Partager'),
            );
    }
    return PopupMenuButton<String>(
      tooltip: 'Partager cette possibilité',
      enabled: !_busy,
      onSelected: (value) {
        if (value == 'makolo') {
          if (widget.authenticated) {
            _internal();
          } else {
            widget.onSignIn?.call();
          }
        } else if (value == 'external') {
          _external();
        } else if (value == 'copy') {
          _copy();
        } else if (value == 'qr') {
          _qr();
        }
      },
      itemBuilder: (_) => [
        PopupMenuItem(
          value: 'makolo',
          child: Text(
            widget.authenticated
                ? 'Dans Makolo'
                : 'Dans Makolo · connexion requise',
          ),
        ),
        PopupMenuItem(value: 'external', child: Text('Partager avec…')),
        PopupMenuItem(value: 'copy', child: Text('Copier le lien')),
        PopupMenuItem(value: 'qr', child: Text('Afficher le QR')),
      ],
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (_busy)
            const SizedBox(
              width: 19,
              height: 19,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else
            const Icon(Icons.share_outlined),
          if (!widget.iconOnly) ...[
            const SizedBox(height: 3),
            const Text('Partager', textAlign: TextAlign.center),
          ],
        ],
      ),
    );
  }
}

class _ShareRecipientPicker extends StatefulWidget {
  const _ShareRecipientPicker({
    required this.api,
    required this.endpoint,
    required this.onDelivered,
  });

  final MakoloApiClient api;
  final String endpoint;
  final VoidCallback onDelivered;

  @override
  State<_ShareRecipientPicker> createState() => _ShareRecipientPickerState();
}

class _ShareRecipientPickerState extends State<_ShareRecipientPicker> {
  final TextEditingController _controller = TextEditingController();
  List<Map<String, dynamic>> _results = const [];
  String? _error;
  bool _loading = false;
  String? _sending;
  int _generation = 0;
  Timer? _debounce;

  @override
  void dispose() {
    _generation++;
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _scheduleSearch(String input) {
    _debounce?.cancel();
    if (input.trim().length < 2) {
      _search(input);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 320), () => _search(input));
  }

  Future<void> _search(String input) async {
    final generation = ++_generation;
    final query = input.trim();
    if (query.length < 2) {
      setState(() {
        _results = const [];
        _error = null;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await widget.api.get(
        'api/v1/sharing/recipients/?q=${Uri.encodeQueryComponent(query)}',
      );
      final data = response.jsonObject()['results'];
      if (!mounted || generation != _generation) return;
      setState(
        () => _results = data is List
            ? data
                  .whereType<Map>()
                  .map((p) => Map<String, dynamic>.from(p))
                  .toList()
            : const [],
      );
    } on Object {
      if (!mounted || generation != _generation) return;
      setState(() => _error = 'Recherche indisponible.');
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _send(String id) async {
    if (_sending != null) return;
    setState(() {
      _sending = id;
      _error = null;
    });
    try {
      final response = await widget.api.post(
        widget.endpoint,
        body: {'recipient_id': id, 'intent': 'view'},
      );
      if (response.jsonObject()['state'] != 'delivered') {
        throw const FormatException('Unexpected share delivery response');
      }
      if (!mounted) return;
      Navigator.of(context).pop();
      widget.onDelivered();
    } on Object {
      if (mounted) setState(() => _error = 'Envoi non confirmé.');
    } finally {
      if (mounted) setState(() => _sending = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          8,
          16,
          MediaQuery.viewInsetsOf(context).bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Partager dans Makolo',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _controller,
              autofocus: true,
              onChanged: _scheduleSearch,
              decoration: const InputDecoration(
                labelText: 'Rechercher un Profil',
                hintText: 'Nom ou identifiant',
                prefixIcon: Icon(Icons.search),
              ),
            ),
            if (_loading) const LinearProgressIndicator(),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.all(8),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                children: [
                  for (final person in _results)
                    ListTile(
                      title: Text((person['name'] ?? '').toString()),
                      subtitle: Text('@${person['username'] ?? ''}'),
                      enabled: _sending == null,
                      trailing: _sending == person['id']
                          ? const CircularProgressIndicator()
                          : const Icon(Icons.send_outlined),
                      onTap: () => _send(person['id'].toString()),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
