import 'package:flutter/material.dart';

import 'makolo_theme.dart';

class MakoloLoadingState extends StatelessWidget {
  const MakoloLoadingState({super.key, this.label = 'Chargement…'});

  final String label;

  @override
  Widget build(BuildContext context) => Center(
        child: Semantics(
          liveRegion: true,
          label: label,
          child: const CircularProgressIndicator(),
        ),
      );
}

class MakoloEmptyState extends StatelessWidget {
  const MakoloEmptyState({
    super.key,
    required this.title,
    this.body,
    this.icon = Icons.check_circle_outline,
  });

  final String title;
  final String? body;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 36),
              const SizedBox(height: MakoloSpacing.md),
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              if (body != null) ...[
                const SizedBox(height: MakoloSpacing.sm),
                Text(
                  body!,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ],
          ),
        ),
      );
}

class MakoloErrorState extends StatelessWidget {
  const MakoloErrorState({
    super.key,
    required this.message,
    this.onRetry,
  });

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 36),
              const SizedBox(height: MakoloSpacing.md),
              Text(message, textAlign: TextAlign.center),
              if (onRetry != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                FilledButton(
                  onPressed: onRetry,
                  child: const Text('Réessayer'),
                ),
              ],
            ],
          ),
        ),
      );
}

class OfflineBanner extends StatelessWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context) => Semantics(
        liveRegion: true,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(
            horizontal: MakoloSpacing.md,
            vertical: MakoloSpacing.sm,
          ),
          color: MakoloColors.warning.withValues(alpha: 0.12),
          child: const Text(
            'Hors connexion · Makolo continue avec ce qui est disponible sur cet appareil.',
            textAlign: TextAlign.center,
          ),
        ),
      );
}

class InlineMessage extends StatelessWidget {
  const InlineMessage({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(MakoloRadii.medium),
        ),
        child: Text(message),
      );
}
