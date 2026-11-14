import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../app/providers.dart';
import '../navigation/incoming_intent.dart';
import '../platform/sharing/system_share_receiver.dart';
import 'runtime_ingress.dart';

class RuntimeIngressListener extends StatefulWidget {
  const RuntimeIngressListener({
    required this.ingress,
    required this.runtime,
    required this.router,
    required this.child,
    super.key,
  });

  final RuntimeIngress ingress;
  final AppRuntime runtime;
  final GoRouter router;
  final Widget child;

  @override
  State<RuntimeIngressListener> createState() => _RuntimeIngressListenerState();
}

class _RuntimeIngressListenerState extends State<RuntimeIngressListener> {
  StreamSubscription<IncomingIntent>? _subscription;
  StreamSubscription<SharedPayload>? _shareSubscription;
  AndroidSystemShareReceiver? _shareReceiver;
  final IncomingIntentResolver _resolver = const IncomingIntentResolver();

  @override
  void initState() {
    super.initState();
    _listen();
    _listenNativeShares();
    _reopenPendingShare();
  }

  @override
  void didUpdateWidget(RuntimeIngressListener oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.ingress != widget.ingress) {
      _subscription?.cancel();
      _listen();
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.ingress != widget.ingress) {
      _reopenPendingShare();
    }
  }

  void _listen() {
    _subscription = widget.ingress.intents.listen((intent) {
      final resolution = _resolver.resolve(
        intent: intent,
        authenticated: widget.runtime.isAuthenticated,
        recovery: widget.runtime.recovery,
      );
      if (resolution != null) widget.router.go(resolution.route);
    });
  }

  void _reopenPendingShare() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted &&
          widget.runtime.isAuthenticated &&
          widget.ingress.hasPendingShare) {
        widget.router.go('/mark');
      }
    });
  }

  void _listenNativeShares() {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return;
    final receiver = AndroidSystemShareReceiver();
    _shareReceiver = receiver;
    _shareSubscription = receiver.incoming.listen(_receiveShare);
    unawaited(_readInitialShare(receiver));
  }

  Future<void> _readInitialShare(AndroidSystemShareReceiver receiver) async {
    try {
      final payload = await receiver.initial();
      if (mounted && payload != null) _receiveShare(payload);
    } on Object {
      // An unavailable native share channel must not block Makolo.
    }
  }

  void _receiveShare(SharedPayload payload) {
    final profile = widget.runtime.isAuthenticated
        ? widget.runtime.session?.profileId
        : null;
    widget.ingress.offerShare(payload, profileId: profile);
    if (widget.runtime.isAuthenticated) {
      widget.router.go('/mark');
    } else {
      widget.runtime.recovery.requireAuthenticationFor('/mark');
      widget.router.go('/login');
    }
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _shareSubscription?.cancel();
    final receiver = _shareReceiver;
    if (receiver != null) unawaited(receiver.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
