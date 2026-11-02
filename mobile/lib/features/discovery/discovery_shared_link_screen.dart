import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';

/// Resolve an opaque, revocable Sharing link before opening public Discovery N2.
/// The server alone determines which public possibility still exists.
class DiscoverySharedLinkScreen extends StatefulWidget {
  const DiscoverySharedLinkScreen({
    super.key,
    required this.runtime,
    this.token,
    this.deliveryId,
  });

  final AppRuntime runtime;
  final String? token;
  final String? deliveryId;

  @override
  State<DiscoverySharedLinkScreen> createState() =>
      _DiscoverySharedLinkScreenState();
}

class _DiscoverySharedLinkScreenState extends State<DiscoverySharedLinkScreen> {
  String? _error;
  int _requestGeneration = 0;

  @override
  void initState() {
    super.initState();
    _resolve();
  }

  @override
  void didUpdateWidget(covariant DiscoverySharedLinkScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.token != widget.token ||
        oldWidget.deliveryId != widget.deliveryId) {
      _resolve();
    }
  }

  @override
  void dispose() {
    _requestGeneration++;
    super.dispose();
  }

  Future<void> _resolve() async {
    final generation = ++_requestGeneration;
    if (mounted) setState(() => _error = null);
    final delivery = widget.deliveryId;
    if (delivery != null && !widget.runtime.isAuthenticated) {
      // Deliveries are private: resume the same opaque reference after login.
      widget.runtime.recovery.requireAuthentication(
        '/shares/${Uri.encodeComponent(delivery)}',
      );
      if (mounted) context.go('/login');
      return;
    }
    try {
      final api = widget.runtime.api;
      if (api == null) throw const FormatException('API unavailable');
      final deliveryId = widget.deliveryId;
      final token = widget.token;
      if (deliveryId == null && token == null) {
        throw const FormatException('Missing share reference');
      }
      final response = deliveryId != null
          ? await api.get(
              'api/v1/sharing/deliveries/${Uri.encodeComponent(deliveryId)}/',
            )
          : await api.publicGet(
              'api/v1/sharing/resolve/${Uri.encodeComponent(token!)}/',
            );
      final payload = response.jsonObject();
      final family = payload['family'];
      final id = payload['id'];
      if (family is! String ||
          id is! String ||
          !{
            'activity',
            'service_activity',
            'funding_activity',
            'opportunity',
          }.contains(family) ||
          id.isEmpty) {
        throw const FormatException('Invalid Sharing destination');
      }
      final expected =
          '/discover/items/${Uri.encodeComponent(family)}/'
          '${Uri.encodeComponent(id)}';
      if (payload['route'] != expected) {
        throw const FormatException('Unexpected Sharing route');
      }
      if (!mounted || generation != _requestGeneration) return;
      context.go(expected);
    } on Object {
      if (mounted && generation == _requestGeneration) {
        setState(() => _error = 'Ce partage n’est plus disponible.');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Partage Makolo')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          child: _error == null
              ? const CircularProgressIndicator()
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: MakoloSpacing.md),
                    TextButton(
                      onPressed: () => context.go('/discover'),
                      child: const Text('Découvrir'),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}
