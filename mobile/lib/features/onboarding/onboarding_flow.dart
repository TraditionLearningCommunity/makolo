import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

enum OnboardingExit {
  skip,
  signIn,
  createAccount,
  continueGuest,
  continueAuthenticated,
}

class OnboardingFlow extends StatelessWidget {
  const OnboardingFlow({
    super.key,
    required this.isAuthenticated,
    required this.onComplete,
  });

  final bool isAuthenticated;
  final Future<void> Function(OnboardingExit exit) onComplete;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Semantics(
          container: true,
          label: 'Bienvenue dans Makolo',
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(MakoloSpacing.xl),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: math.max(
                  0,
                  MediaQuery.sizeOf(context).height - (MakoloSpacing.xl * 2),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Align(
                    alignment: Alignment.centerLeft,
                    child: MakoloMark(size: 64),
                  ),
                  const SizedBox(height: MakoloSpacing.xl),
                  Text(
                    'Découvrir.\nPréparer.\nAvancer.',
                    style: Theme.of(context).textTheme.headlineSmall
                        ?.copyWith(fontSize: 34, height: 1.16),
                  ),
                  const SizedBox(height: MakoloSpacing.lg),
                  Text(
                    'Makolo vous aide à trouver ce qui compte et à avancer dans l’action réelle.',
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                  const SizedBox(height: MakoloSpacing.xl),
                  FilledButton(
                    key: const Key('onboarding-primary'),
                    onPressed: () => onComplete(
                      isAuthenticated
                          ? OnboardingExit.continueAuthenticated
                          : OnboardingExit.continueGuest,
                    ),
                    child: Text(
                      isAuthenticated ? 'Ouvrir Makolo' : 'Découvrir Makolo',
                    ),
                  ),
                  if (!isAuthenticated) ...[
                    const SizedBox(height: MakoloSpacing.md),
                    OutlinedButton(
                      onPressed: () => onComplete(OnboardingExit.signIn),
                      child: const Text('Se connecter'),
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    TextButton(
                      onPressed: () => onComplete(OnboardingExit.createAccount),
                      child: const Text('Créer un compte'),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
