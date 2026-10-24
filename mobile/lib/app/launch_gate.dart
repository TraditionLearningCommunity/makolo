import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../features/onboarding/onboarding_flow.dart';
import '../features/splash/splash_screen.dart';
import 'launch_policy.dart';
import 'launch_preferences.dart';
import 'providers.dart';

enum _LaunchStage { preparing, onboarding, content }

// The first Flutter frame is never deferred. Android's single native splash
// is released only after a real destination (or recoverable error) is drawn.
void releaseNativeLaunchAfterFrame() {
  if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return;
  WidgetsBinding.instance.addPostFrameCallback((_) {
    unawaited(_releaseNativeLaunch());
  });
}

Future<void> _releaseNativeLaunch() async {
  try {
    await const MethodChannel('makolo/launch').invokeMethod<void>('ready');
  } on MissingPluginException {
    // Widget tests and hosts without the Android launch bridge use the fallback.
  }
}

class LaunchGate extends StatefulWidget {
  const LaunchGate({
    super.key,
    required this.runtime,
    required this.router,
    required this.child,
  });

  final AppRuntime runtime;
  final GoRouter router;
  final Widget child;

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

    if (!mounted) return;

    final path = widget.router.routeInformationProvider.value.uri.path;

    final priorityNavigation = hasPriorityLaunchPath(
      path,
      authenticated: widget.runtime.isAuthenticated,
    );

    setState(() {
      _preferences = preferences;
      _priorityNavigation = priorityNavigation;
      _stage = _destinationStage(preferences);
    });
    releaseNativeLaunchAfterFrame();
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
        if (!_priorityNavigation) {
          widget.router.go('/welcome');
        }

      case OnboardingExit.continueAuthenticated:
        if (!_priorityNavigation) {
          widget.router.go('/now');
        }
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
        location: widget.runtime.location,
        onComplete: _finishOnboarding,
      ),

      _LaunchStage.content => widget.child,
    };
  }
}
