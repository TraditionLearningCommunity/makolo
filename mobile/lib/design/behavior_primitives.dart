import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../sync/sync_status.dart';
import 'makolo_theme.dart';

class MakoloSkeleton extends StatelessWidget {
  const MakoloSkeleton({
    super.key,
    this.lines = 4,
    this.lineHeight = 16,
  });

  final int lines;
  final double lineHeight;

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final color = Theme.of(
      context,
    ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.7);

    return Semantics(
      label: 'Chargement du contenu',
      liveRegion: true,
      child: ExcludeSemantics(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: List.generate(lines, (index) {
              final widthFactor = index == lines - 1 ? 0.58 : 1.0;
              return Padding(
                padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                child: AnimatedContainer(
                  duration: reduceMotion
                      ? Duration.zero
                      : MakoloMotion.short,
                  height: lineHeight,
                  width: double.infinity,
                  constraints: const BoxConstraints(minWidth: 48),
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(MakoloRadii.small),
                  ),
                  child: FractionallySizedBox(
                    widthFactor: widthFactor,
                    alignment: Alignment.centerLeft,
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}

enum SuccessFeedbackKind {
  savedOnDevice,
  pendingSync,
  synced,
  confirmed,
}

class SuccessFeedback extends StatelessWidget {
  const SuccessFeedback({
    super.key,
    required this.kind,
    this.compact = false,
  });

  final SuccessFeedbackKind kind;
  final bool compact;

  String get _label => switch (kind) {
    SuccessFeedbackKind.savedOnDevice => 'Enregistré sur cet appareil',
    SuccessFeedbackKind.pendingSync => 'En attente de synchronisation',
    SuccessFeedbackKind.synced => 'Synchronisé',
    SuccessFeedbackKind.confirmed => 'Confirmé',
  };

  IconData get _icon => switch (kind) {
    SuccessFeedbackKind.savedOnDevice => Icons.save_outlined,
    SuccessFeedbackKind.pendingSync => Icons.schedule_outlined,
    SuccessFeedbackKind.synced => Icons.cloud_done_outlined,
    SuccessFeedbackKind.confirmed => Icons.check_circle_outline,
  };

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: _label,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(_icon, size: compact ? 16 : 20),
        const SizedBox(width: MakoloSpacing.sm),
        Flexible(child: Text(_label)),
      ],
    ),
  );
}

class NetworkStateIndicator extends StatelessWidget {
  const NetworkStateIndicator({super.key, required this.status});

  final SyncStatus status;

  String get _label => switch (status.state) {
    SyncVisualState.synced => 'À jour',
    SyncVisualState.syncing => 'Mise à jour…',
    SyncVisualState.pending => status.pendingCount > 1
        ? '${status.pendingCount} actions en attente de synchronisation'
        : 'En attente de synchronisation',
    SyncVisualState.offline => 'Hors connexion',
    SyncVisualState.conflict => 'Une modification demande votre attention',
    SyncVisualState.failed => 'Impossible de synchroniser pour le moment',
    SyncVisualState.stale => 'Données disponibles, vérification nécessaire',
  };

  IconData get _icon => switch (status.state) {
    SyncVisualState.synced => Icons.cloud_done_outlined,
    SyncVisualState.syncing => Icons.sync,
    SyncVisualState.pending => Icons.schedule_outlined,
    SyncVisualState.offline => Icons.cloud_off_outlined,
    SyncVisualState.conflict => Icons.compare_arrows_outlined,
    SyncVisualState.failed => Icons.sync_problem_outlined,
    SyncVisualState.stale => Icons.history_toggle_off_outlined,
  };

  @override
  Widget build(BuildContext context) {
    if (status.state == SyncVisualState.synced) {
      return const SizedBox.shrink();
    }
    return Semantics(
      liveRegion: true,
      label: _label,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.md,
          vertical: MakoloSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(MakoloRadii.small),
        ),
        child: Row(
          children: [
            Icon(_icon, size: 18),
            const SizedBox(width: MakoloSpacing.sm),
            Expanded(child: Text(_label)),
          ],
        ),
      ),
    );
  }
}

void showMakoloToast(
  BuildContext context,
  String message, {
  Duration duration = const Duration(seconds: 3),
}) {
  final messenger = ScaffoldMessenger.of(context);
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message), duration: duration));
}

void showMakoloUndoToast(
  BuildContext context, {
  required String message,
  required VoidCallback onUndo,
  String undoLabel = 'Annuler',
}) {
  final messenger = ScaffoldMessenger.of(context);
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(message),
        action: SnackBarAction(label: undoLabel, onPressed: onUndo),
      ),
    );
}

Future<bool> showMakoloConfirmationDialog(
  BuildContext context, {
  required String title,
  required String message,
  String confirmLabel = 'Confirmer',
  String cancelLabel = 'Annuler',
  bool destructive = false,
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(cancelLabel),
        ),
        FilledButton(
          style: destructive
              ? FilledButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.error,
                )
              : null,
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return result ?? false;
}

Future<T?> showMakoloBottomSheet<T>(
  BuildContext context, {
  required WidgetBuilder builder,
}) {
  return showModalBottomSheet<T>(
    context: context,
    useSafeArea: true,
    isScrollControlled: true,
    showDragHandle: true,
    builder: builder,
  );
}

class PermissionExplainer extends StatelessWidget {
  const PermissionExplainer({
    super.key,
    required this.title,
    required this.message,
    required this.actionLabel,
    required this.onContinue,
    this.denied = false,
    this.deniedMessage,
  });

  final String title;
  final String message;
  final String actionLabel;
  final VoidCallback onContinue;
  final bool denied;
  final String? deniedMessage;

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    child: Padding(
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: MakoloSpacing.sm),
          Text(message),
          if (denied) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text(
              deniedMessage ??
                  'Cette autorisation est refusée. Vous pouvez continuer sans cette fonction et la réactiver plus tard si nécessaire.',
            ),
          ],
          const SizedBox(height: MakoloSpacing.lg),
          FilledButton(onPressed: onContinue, child: Text(actionLabel)),
        ],
      ),
    ),
  );
}

abstract final class MakoloHaptics {
  static Future<void> selection() => HapticFeedback.selectionClick();
  static Future<void> success() => HapticFeedback.lightImpact();
  static Future<void> warning() => HapticFeedback.mediumImpact();
}
