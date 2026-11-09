import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:pretty_qr_code/pretty_qr_code.dart';

import '../../network/api_error.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/sharing/share_gateway.dart';
import 'discovery_selector.dart';

/// Production Sharing links require HTTPS. Only local Django testing may
/// use HTTP: loopback, or a private LAN address matching the configured API.
bool _privateIpv4(String host) {
  final segments = host.split('.');
  if (segments.length != 4) return false;
  final octets = segments.map(int.tryParse).toList();
  if (octets.any((part) => part == null || part < 0 || part > 255)) {
    return false;
  }
  final first = octets[0]!;
  final second = octets[1]!;
  return first == 10 ||
      (first == 172 && second >= 16 && second <= 31) ||
      (first == 192 && second == 168);
}

Uri? discoverySharePublicUri(String? raw, {Uri? trustedBaseUri}) {
  if (raw == null || raw.isEmpty) return null;
  final uri = Uri.tryParse(raw);
  if (uri == null ||
      !uri.hasAuthority ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty) {
    return null;
  }
  if (uri.scheme == 'https') return uri;
  if (uri.scheme != 'http') return null;
  if (uri.host == 'localhost' ||
      uri.host == '127.0.0.1' ||
      uri.host == '[::1]' ||
      uri.host == '::1') {
    return uri;
  }
  if (_privateIpv4(uri.host) &&
      trustedBaseUri?.scheme == 'http' &&
      trustedBaseUri?.origin == uri.origin) {
    return uri;
  }
  return null;
}

/// Reuses the canonical Sharing owner API; no local envelope or fake delivery.
class DiscoveryShareControl extends StatefulWidget {
  const DiscoveryShareControl({
    super.key,
    required this.item,
    required this.api,
    required this.authenticated,
    this.onSignIn,
    this.iconOnly = false,
    this.enabled = true,
    this.showAsSheet = false,
    this.baseUri,
  });

  final DiscoveryItemPresentation item;
  final MakoloApiClient? api;
  final bool authenticated;
  final VoidCallback? onSignIn;
  final bool iconOnly;

  /// The owner has been revalidated for this N2; cached facts alone never
  /// authorize fresh sharing. N1 keeps its established behavior.
  final bool enabled;

  /// Carte uses the same Sharing operations but places choices in a
  /// bottom sheet rather than obscuring a short map preview with a popup.
  final bool showAsSheet;
  final Uri? baseUri;

  @override
  State<DiscoveryShareControl> createState() => _DiscoveryShareControlState();
}

class _DiscoveryShareControlState extends State<DiscoveryShareControl> {
  bool _busy = false;
  Map<String, dynamic>? _created;
  int _itemGeneration = 0;

  @override
  void didUpdateWidget(covariant DiscoveryShareControl oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.family != widget.item.family ||
        oldWidget.item.id != widget.item.id ||
        oldWidget.api != widget.api ||
        oldWidget.baseUri != widget.baseUri ||
        oldWidget.authenticated != widget.authenticated ||
        oldWidget.enabled != widget.enabled) {
      // Opaque share tokens are bound to one owner identity and sender.
      ++_itemGeneration;
      _created = null;
    }
  }

  String get _endpoint =>
      'api/v1/sharing/possibilities/'
      '${Uri.encodeComponent(widget.item.family)}/'
      '${Uri.encodeComponent(widget.item.id)}/';

  Uri? get _shareUrl {
    final text = _created?['url'];
    return text is String
        ? discoverySharePublicUri(text, trustedBaseUri: widget.baseUri)
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

  @override
  void dispose() {
    ++_itemGeneration;
    super.dispose();
  }

  void _feedback(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _action(Future<void> Function() task) async {
    if (_busy || !widget.enabled) return;
    final generation = _itemGeneration;
    setState(() => _busy = true);
    try {
      await task();
    } on MakoloApiError catch (error) {
      if (generation == _itemGeneration) {
        final message = switch (error.statusCode) {
          401 => 'Connectez-vous pour partager.',
          403 => 'Vous ne pouvez pas partager cette opportunité.',
          404 => 'Cette opportunité n’est plus partageable.',
          429 => 'Trop de partages. Réessayez plus tard.',
          _ => 'Le partage n’a pas pu aboutir. Réessayez.',
        };
        _feedback(message);
      }
    } on Object {
      if (generation == _itemGeneration) {
        _feedback('Le partage n’a pas pu aboutir. Réessayez.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<Uri> _link() async {
    if (!widget.enabled) throw StateError('Sharing not verified');
    if (_shareUrl != null) return _shareUrl!;
    final api = widget.api;
    if (!widget.authenticated) {
      // Guests may share an explicitly public link, never a private delivery.
      final publicUrl = _publicItemUrl;
      if (publicUrl == null) throw StateError('Public share URL unavailable');
      return publicUrl;
    }
    if (api == null) {
      throw StateError('Sharing authority unavailable');
    }
    // Authenticated shares are always owner-confirmed. Missing web_share does
    // not authorize silently falling back to an unverified public URL.
    final generation = _itemGeneration;
    final endpoint = _endpoint;
    final result = await api.post(endpoint, body: {'intent': 'view'});
    final data = result.jsonObject();
    if (data['state'] != 'link') {
      throw const FormatException('Unexpected share contract');
    }
    if (!mounted || generation != _itemGeneration) {
      throw StateError('Share candidate changed during request');
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

  Future<void> _internal() => _action(() async {
    final api = widget.api;
    if (api == null || !widget.authenticated) {
      throw StateError('Sharing authority unavailable');
    }
    // Internal sharing goes through the same guarded, owner-confirmed
    // operation as Copy, QR and external sharing. Exceptions from the
    // recipient sheet must not escape an unawaited popup callback.
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
  });

  void _selectAction(String value) {
    if (value == 'makolo') {
      if (widget.authenticated) {
        unawaited(_internal());
      } else {
        widget.onSignIn?.call();
      }
    } else if (value == 'external') {
      unawaited(_external());
    } else if (value == 'copy') {
      unawaited(_copy());
    } else if (value == 'qr') {
      unawaited(_qr());
    }
  }

  Future<void> _openOptionsSheet() async {
    if (_busy || !widget.enabled) return;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      useSafeArea: true,
      builder: (sheetContext) {
        void choose(String action) {
          Navigator.of(sheetContext).pop();
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) _selectAction(action);
          });
        }

        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.authenticated || widget.onSignIn != null)
                  ListTile(
                    leading: const Icon(Icons.people_outline_rounded),
                    title: Text(
                      widget.authenticated
                          ? 'Dans Makolo'
                          : 'Dans Makolo · connexion requise',
                    ),
                    onTap: () => choose('makolo'),
                  ),
                ListTile(
                  leading: const Icon(Icons.ios_share_rounded),
                  title: const Text('Partager avec…'),
                  onTap: () => choose('external'),
                ),
                ListTile(
                  leading: const Icon(Icons.link_rounded),
                  title: const Text('Copier le lien'),
                  onTap: () => choose('copy'),
                ),
                ListTile(
                  leading: const Icon(Icons.qr_code_rounded),
                  title: const Text('Afficher le QR'),
                  onTap: () => choose('qr'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    // The owner Web share reference is the current contract for shareability.
    // Presence of a public card alone never grants sharing authority.
    if (!widget.enabled ||
        (widget.authenticated && widget.api == null) ||
        (!widget.authenticated && _publicItemUrl == null) ||
        (widget.authenticated &&
            widget.item.links['web'] == null &&
            widget.item.links['web_share'] == null)) {
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
    if (widget.showAsSheet) {
      return IconButton(
        tooltip: 'Partager l’opportunité',
        onPressed: _busy ? null : () => unawaited(_openOptionsSheet()),
        icon: _busy
            ? const SizedBox(
                width: 19,
                height: 19,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.share_outlined),
      );
    }
    return PopupMenuButton<String>(
      tooltip: 'Partager l’opportunité',
      enabled: widget.enabled && !_busy,
      onSelected: _selectAction,
      icon: widget.iconOnly
          ? Icon(_busy ? Icons.hourglass_top_rounded : Icons.share_outlined)
          : null,
      itemBuilder: (_) => [
        if (widget.authenticated || widget.onSignIn != null)
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
      child: widget.iconOnly
          ? null
          : Column(
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
      final payload = response.jsonObject();
      if (payload['state'] != 'delivered' ||
          payload['delivery_id'] is! String ||
          (payload['delivery_id'] as String).trim().isEmpty) {
        throw const FormatException('Sharing delivery not confirmed');
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
