import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class GuestDiscoverScreen extends StatelessWidget {
  const GuestDiscoverScreen({super.key, required this.isAuthenticated});

  final bool isAuthenticated;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        Row(
          children: [
            const MakoloMark(size: 36),
            const SizedBox(width: MakoloSpacing.md),
            Expanded(
              child: Text(
                'Découvrir',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ),
          ],
        ),
        const SizedBox(height: MakoloSpacing.xl),
        Text(
          'Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: MakoloSpacing.lg),
        const Wrap(
          spacing: MakoloSpacing.sm,
          runSpacing: MakoloSpacing.sm,
          children: [
            Chip(label: Text('Services')),
            Chip(label: Text('Transports')),
            Chip(label: Text('Événements')),
          ],
        ),
        const SizedBox(height: MakoloSpacing.lg),
        const Text(
          'Les possibilités publiques disponibles apparaîtront ici. Cette surface reste accessible sans compte.',
        ),
        if (!isAuthenticated) ...[
          const SizedBox(height: MakoloSpacing.xl),
          FilledButton(
            onPressed: () => context.push('/login'),
            child: const Text('Se connecter'),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          OutlinedButton(
            onPressed: () => context.push('/create-account'),
            child: const Text('Créer un compte'),
          ),
        ],
      ],
    );
  }
}

class GuestPersonalScreen extends StatelessWidget {
  const GuestPersonalScreen({
    super.key,
    required this.title,
    required this.message,
  });

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        Text(title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: MakoloSpacing.md),
        Text(message),
        const SizedBox(height: MakoloSpacing.xl),
        FilledButton(
          onPressed: () => context.push('/login'),
          child: const Text('Se connecter'),
        ),
        const SizedBox(height: MakoloSpacing.sm),
        OutlinedButton(
          onPressed: () => context.push('/create-account'),
          child: const Text('Créer un compte'),
        ),
        const SizedBox(height: MakoloSpacing.sm),
        TextButton(
          onPressed: () => context.go('/discover'),
          child: const Text('Découvrir sans compte'),
        ),
      ],
    );
  }
}
