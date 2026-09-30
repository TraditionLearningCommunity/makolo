import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/onboarding/onboarding_flow.dart';
import '../features/splash/splash_screen.dart';
import 'launch_policy.dart';
import 'launch_preferences.dart';
import 'providers.dart';

enum _LaunchStage { preparing, onboarding, content }

class LaunchGate extends StatefulWidget {
  const LaunchGate({
    super.key,
    required this.runtime,
    required this.router,
    required this.child,
    this.launchStartedAt,
    this.minimumVisible = const Duration(seconds: 1),
  });

  final AppRuntime runtime;
  final GoRouter router;
  final Widget child;
  final DateTime? launchStartedAt;
  final Duration minimumVisible;

  @override
  State<LaunchGate> createState() => _LaunchGateState();
}

class _LaunchGateState extends State<LaunchGate> {
  _LaunchStage _stage = _LaunchStage.preparing;
  LaunchPreferencesSnapshot _preferences = const LaunchPreferencesSnapshot();
  bool _priorityNavigation = false;
  late final Future<void> _minimumVisibleFuture;

  @override
  void initState() {
    super.initState();
    final startedAt = widget.launchStartedAt ?? DateTime.now();
    final elapsed = DateTime.now().difference(startedAt);
    final remaining = widget.minimumVisible - elapsed;
    _minimumVisibleFuture = remaining > Duration.zero
        ? Future<void>.delayed(remaining)
        : Future<void>.value();
    _prepare();
  }

  Future<void> _prepare() async {
    final store = widget.runtime.launchPreferences;
    if (store == null) {
      await _minimumVisibleFuture;
      if (mounted) setState(() => _stage = _LaunchStage.content);
      return;
    }
    final preferences = await store.read();
    final path = widget.router.routeInformationProvider.value.uri.path;
    await _minimumVisibleFuture;
    if (!mounted) return;

    final priorityNavigation = hasPriorityLaunchPath(
      path,
      authenticated: widget.runtime.isAuthenticated,
    );
    setState(() {
      _preferences = preferences;
      _priorityNavigation = priorityNavigation;
      _stage = preferences.hasCompletedOnboarding
          ? _LaunchStage.content
          : _LaunchStage.onboarding;
    });
  }

  Future<void> _finishOnboarding(OnboardingExit exit) async {
    await widget.runtime.launchPreferences?.setOnboardingCompleted();
    if (!mounted) return;

    switch (exit) {
      case OnboardingExit.signIn:
        widget.router.go('/login');
      case OnboardingExit.createAccount:
        widget.router.go('/create-account');
      case OnboardingExit.skip:
      case OnboardingExit.continueGuest:
        if (!_priorityNavigation) widget.router.go('/discover');
      case OnboardingExit.continueAuthenticated:
        if (!_priorityNavigation) widget.router.go('/now');
    }

    setState(() {
      _preferences = _preferences.copyWith(hasCompletedOnboarding: true);
      _stage = _LaunchStage.content;
    });
  }

  @override
  Widget build(BuildContext context) {
    return switch (_stage) {
      _LaunchStage.preparing => const SplashScreen(),
      _LaunchStage.onboarding => OnboardingFlow(
        isAuthenticated: widget.runtime.isAuthenticated,
        onComplete: _finishOnboarding,
      ),
      _LaunchStage.content => widget.child,
    };
  }
}
