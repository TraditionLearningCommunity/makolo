import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/onboarding/onboarding_flow.dart';
import '../features/splash/brand_moment.dart';
import '../features/splash/splash_screen.dart';
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
    this.launchStartedAt,
    this.minimumVisible = Duration.zero,
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

  @override
  void initState() {
    super.initState();
    _prepare();
  }

  _LaunchStage _destinationStage(LaunchPreferencesSnapshot preferences) {
    return preferences.hasCompletedOnboarding
        ? _LaunchStage.content
        : _LaunchStage.onboarding;
  }

  Future<void> _prepare() async {
    final store = widget.runtime.launchPreferences;
    final preferences =
        await store?.read() ?? const LaunchPreferencesSnapshot();
    if (widget.minimumVisible > Duration.zero) {
      await Future<void>.delayed(widget.minimumVisible);
    }
    if (!mounted) return;

    final path = widget.router.routeInformationProvider.value.uri.path;
    final priorityNavigation = hasPriorityLaunchPath(
      path,
      authenticated: widget.runtime.isAuthenticated,
    );
    final showBrandMoment = const BrandMomentPolicy().isEligible(
      preferences: preferences,
      now: DateTime.now(),
      hasPriorityNavigation: priorityNavigation,
    );

    setState(() {
      _preferences = preferences;
      _priorityNavigation = priorityNavigation;
      _stage = showBrandMoment
          ? _LaunchStage.brandMoment
          : _destinationStage(preferences);
    });
  }

  Future<void> _finishBrandMoment() async {
    final shownAt = DateTime.now().toUtc();
    await widget.runtime.launchPreferences?.setLastBrandMomentAt(shownAt);
    if (!mounted) return;
    final updated = _preferences.copyWith(lastBrandMomentAt: shownAt);
    setState(() {
      _preferences = updated;
      _stage = _destinationStage(updated);
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
