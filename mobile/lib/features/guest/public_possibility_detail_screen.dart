import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../discovery/discovery_selector.dart';
import '../discovery/discovery_wire.dart';
import '../../presentation/possibilities/discovery_possibility_unit.dart';
import 'public_shell.dart';

/// Read-only, server-authorized guest depth. A personal operation always
/// crosses the authentication boundary; it cannot be simulated locally.
class PublicPossibilityDetailScreen extends StatefulWidget {
  const PublicPossibilityDetailScreen({
    super.key,
    required this.runtime,
    required this.family,
    required this.id,
  });

  final AppRuntime runtime;
  final String family;
  final String id;

  @override
  State<PublicPossibilityDetailScreen> createState() =>
      _PublicPossibilityDetailScreenState();
}

class _PublicPossibilityDetailScreenState
    extends State<PublicPossibilityDetailScreen> {
  static const _selector = DiscoverySelector();
  DiscoveryItemPresentation? _item;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant PublicPossibilityDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.family != widget.family || oldWidget.id != widget.id) {
      _item = null;
      unawaited(_load());
    }
  }

  Future<void> _load() async {
    final family = widget.family;
    final id = widget.id;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      final response = await api.publicGet(
        'api/v1/discovery/items/${Uri.encodeComponent(widget.family)}/'
        '${Uri.encodeComponent(widget.id)}/',
      );
      final raw = DiscoveryWire.receiveItem(
        response.jsonObject(),
        scope: 'public',
      );
      final identity = raw['identity'] as Map;
      final resource = identity['resource'] as Map;
      if (identity['family'] != family || resource['id'] != id) {
        throw const FormatException('Unexpected Discovery detail identity');
      }
      final item = _selector.publicItem(raw);
      if (item == null) throw const FormatException('Unknown possibility');
      if (!mounted || widget.family != family || widget.id != id) return;
      setState(() {
        _item = item;
        _loading = false;
      });
    } on Object {
      if (!mounted || widget.family != family || widget.id != id) return;
      setState(() {
        _loading = false;
        _error = 'Cette possibilité publique n’est pas disponible.';
      });
    }
  }

  void _requireAuthentication() {
    final path = '/discover/items/${widget.family}/${widget.id}';
    widget.runtime.recovery.requireAuthentication(path);
    context.push('/login');
  }

  @override
  Widget build(BuildContext context) {
    final item = _item;
    return PublicExperienceShell(
      current: 1,
      child: ListView(
        key: const Key('guest-possibility-detail'),
        padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.inner,
            ),
            child: Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () {
                  if (context.canPop()) {
                    context.pop();
                  } else {
                    context.go('/discover');
                  }
                },
                icon: const Icon(Icons.arrow_back),
                label: const Text('Retour à Découvrir'),
              ),
            ),
          ),
          if (_loading && item == null)
            const Center(child: CircularProgressIndicator())
          else if (_error != null && item == null) ...[
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.inner,
              ),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
            TextButton(onPressed: _load, child: const Text('Réessayer')),
          ] else if (item != null)
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1040),
                child: DiscoveryPossibilityUnit(
                  item: item,
                  detailMode: true,
                  onOpen: () {},
                  allowSavePrompt: true,
                  onSignIn: _requireAuthentication,
                  onNativeAction: (nativePath) {
                    if (discoveryOwnerDepthBrowsableByGuest(nativePath)) {
                      context.push(nativePath);
                    } else {
                      // Re-enter the protected owner depth after session recovery.
                      widget.runtime.recovery.requireAuthentication(nativePath);
                      context.push('/login');
                    }
                  },
                  shareApi: widget.runtime.api,
                  baseUri: widget.runtime.api?.baseUri,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
