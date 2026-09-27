import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/onboarding/onboarding_flow.dart';
import '../features/splash/brand_moment.dart';
import '../features/splash/splash_screen.dart';
import '../sync/sync_engine.dart';
import 'launch_policy.dart';
import 'launch_preferences.dart';
import 'providers.dart';

enum _LaunchStage { preparing, brandMoment, onboarding, content }

class LaunchGate extends StatefulWidget {
  const LaunchGate({
    super.key,
    required this.runtime,
    required this.router,
    required this.child,
    this.brandPolicy = const BrandMomentPolicy(),
    this.launchStartedAt,
    this.minimumVisible = const Duration(milliseconds: 700),
  });

  final AppRuntime runtime;
  final GoRouter router;
  final Widget child;
  final BrandMomentPolicy brandPolicy;
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
    final launchStartedAt = widget.launchStartedAt ?? DateTime.now();
    final elapsed = DateTime.now().difference(launchStartedAt);
    final remaining = widget.minimumVisible - elapsed;
    _minimumVisibleFuture = remaining > Duration.zero
        ? Future<void>.delayed(remaining)
        : Future<void>.value();
    _prepare();
  }

  Future<void> _prepareInitialPersonalSurface(String path) async {
    if (!widget.runtime.isAuthenticated) return;
    final store = widget.runtime.store;
    final sync = widget.runtime.sync;
    if (store == null || sync == null) return;

    final SyncRoot root = switch (path) {
      '/ongoing' => SyncEngine.roots[1],
      '/me' => SyncEngine.roots[2],
      _ => SyncEngine.roots[0],
    };

    final local = await store.readProjection(root.key);
    if (local != null) return;

    try {
      await sync.pull(root);
    } on Object {
      // A first remote read is best-effort. The local-first shell can still
      // open cleanly and SyncLifecycle will represent offline/error states.
    }
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
    await _prepareInitialPersonalSurface(path);
    await _minimumVisibleFuture;
    if (!mounted) return;

    final priorityNavigation = hasPriorityLaunchPath(
      path,
      authenticated: widget.runtime.isAuthenticated,
    );
    final showBrandMoment = widget.brandPolicy.isEligible(
      preferences: preferences,
      now: DateTime.now(),
      hasPriorityNavigation: priorityNavigation,
    );

    setState(() {
      _preferences = preferences;
      _priorityNavigation = priorityNavigation;
      _stage = showBrandMoment
          ? _LaunchStage.brandMoment
          : preferences.hasCompletedOnboarding
          ? _LaunchStage.content
          : _LaunchStage.onboarding;
    });
  }

  Future<void> _finishBrandMoment() async {
    final shownAt = DateTime.now().toUtc();
    await widget.runtime.launchPreferences?.setLastBrandMomentAt(shownAt);
    if (!mounted) return;

    setState(() {
      _preferences = _preferences.copyWith(lastBrandMomentAt: shownAt);
      _stage = _preferences.hasCompletedOnboarding
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
      _LaunchStage.brandMoment => BrandMoment(onFinished: _finishBrandMoment),
      _LaunchStage.onboarding => OnboardingFlow(
        isAuthenticated: widget.runtime.isAuthenticated,
        onComplete: _finishOnboarding,
      ),
      _LaunchStage.content => widget.child,
    };
  }
}
