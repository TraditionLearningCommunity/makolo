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

class OnboardingFlow extends StatefulWidget {
  const OnboardingFlow({
    super.key,
    required this.isAuthenticated,
    required this.onComplete,
  });

  final bool isAuthenticated;
  final Future<void> Function(OnboardingExit exit) onComplete;

  @override
  State<OnboardingFlow> createState() => _OnboardingFlowState();
}

class _OnboardingFlowState extends State<OnboardingFlow> {
  bool _showAccountChoice = false;

  Future<void> _continue() async {
    if (widget.isAuthenticated) {
      await widget.onComplete(OnboardingExit.continueAuthenticated);
      return;
    }
    setState(() => _showAccountChoice = true);
  }

  @override
  Widget build(BuildContext context) {
    return _showAccountChoice
        ? _AccountChoice(onComplete: widget.onComplete)
        : _Introduction(
            onContinue: _continue,
            onSkip: () => widget.onComplete(OnboardingExit.skip),
          );
  }
}

class _Introduction extends StatelessWidget {
  const _Introduction({required this.onContinue, required this.onSkip});

  final VoidCallback onContinue;
  final VoidCallback onSkip;

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
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: onSkip,
                      child: const Text('Passer'),
                    ),
                  ),
                  const SizedBox(height: MakoloSpacing.lg),
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
                    'Makolo vous aide à trouver des possibilités réelles, préparer ce qui peut l’être et garder la suite claire.',
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                  const SizedBox(height: MakoloSpacing.xl),
                  Wrap(
                    spacing: MakoloSpacing.sm,
                    runSpacing: MakoloSpacing.sm,
                    children: const [
                      Chip(label: Text('Services')),
                      Chip(label: Text('Transports')),
                      Chip(label: Text('Événements')),
                    ],
                  ),
                  const SizedBox(height: MakoloSpacing.xl),
                  FilledButton(
                    onPressed: onContinue,
                    child: const Text('Continuer'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AccountChoice extends StatelessWidget {
  const _AccountChoice({required this.onComplete});

  final Future<void> Function(OnboardingExit exit) onComplete;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Semantics(
          container: true,
          label: 'Choisir comment entrer dans Makolo',
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(MakoloSpacing.xl),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => onComplete(OnboardingExit.skip),
                    child: const Text('Passer'),
                  ),
                ),
                const SizedBox(height: MakoloSpacing.lg),
                const Align(
                  alignment: Alignment.centerLeft,
                  child: MakoloMark(size: 56),
                ),
                const SizedBox(height: MakoloSpacing.xl),
                Text(
                  'Entrez dans Makolo à votre rythme',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  'Un compte permet de retrouver votre activité personnelle, vos éléments en cours et vos données sur vos appareils. Vous pouvez aussi continuer sans compte.',
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: MakoloSpacing.xl),
                FilledButton(
                  onPressed: () => onComplete(OnboardingExit.signIn),
                  child: const Text('Se connecter'),
                ),
                const SizedBox(height: MakoloSpacing.md),
                OutlinedButton(
                  onPressed: () => onComplete(OnboardingExit.createAccount),
                  child: const Text('Créer un compte'),
                ),
                const SizedBox(height: MakoloSpacing.sm),
                TextButton(
                  onPressed: () => onComplete(OnboardingExit.continueGuest),
                  child: const Text('Continuer sans compte'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
