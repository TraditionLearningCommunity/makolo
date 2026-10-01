import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../app/providers.dart';
import '../navigation/incoming_intent.dart';
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
  final IncomingIntentResolver _resolver = const IncomingIntentResolver();

  @override
  void initState() {
    super.initState();
    _listen();
  }

  @override
  void didUpdateWidget(RuntimeIngressListener oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.ingress != widget.ingress) {
      _subscription?.cancel();
      _listen();
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

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
