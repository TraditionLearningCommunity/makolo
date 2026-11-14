import 'package:flutter/material.dart';

import 'makolo_theme.dart';

/// Shared visual action grammar for all primary, secondary and depth surfaces.
///
/// Domain owners select the action and callback. This widget owns only
/// presentation and touch semantics, never access checks or mutation state.
enum MakoloActionAppearance { primary, secondary, quiet, danger }

class MakoloActionButton extends StatelessWidget {
  const MakoloActionButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.appearance = MakoloActionAppearance.secondary,
    this.busy = false,
    this.phase = MakoloActionPhase.available,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final MakoloActionAppearance appearance;
  final bool busy;
  final MakoloActionPhase phase;

  @override
  Widget build(BuildContext context) {
    final effectivePhase = busy ? MakoloActionPhase.processing : phase;
    final waiting = effectivePhase == MakoloActionPhase.processing;
    final unavailable = effectivePhase == MakoloActionPhase.unavailable;
    final handler = waiting || unavailable ? null : onPressed;
    final visibleIcon = switch (effectivePhase) {
      MakoloActionPhase.processing => Icons.hourglass_top_rounded,
      MakoloActionPhase.failed => Icons.error_outline_rounded,
      MakoloActionPhase.confirmed => Icons.check_circle_outline_rounded,
      _ => icon,
    };
    final iconWidget = visibleIcon == null
        ? null
        : MakoloActionFeedback(phase: effectivePhase, child: Icon(visibleIcon));
    final labelWidget = Text(label);
    return switch (appearance) {
      MakoloActionAppearance.primary =>
        iconWidget == null
            ? FilledButton(onPressed: handler, child: labelWidget)
            : FilledButton.icon(
                onPressed: handler,
                icon: iconWidget,
                label: labelWidget,
              ),
      MakoloActionAppearance.secondary =>
        iconWidget == null
            ? OutlinedButton(onPressed: handler, child: labelWidget)
            : OutlinedButton.icon(
                onPressed: handler,
                icon: iconWidget,
                label: labelWidget,
              ),
      MakoloActionAppearance.quiet =>
        iconWidget == null
            ? TextButton(onPressed: handler, child: labelWidget)
            : TextButton.icon(
                onPressed: handler,
                icon: iconWidget,
                label: labelWidget,
              ),
      MakoloActionAppearance.danger =>
        iconWidget == null
            ? OutlinedButton(
                onPressed: handler,
                style: OutlinedButton.styleFrom(
                  foregroundColor: Theme.of(context).colorScheme.error,
                  side: BorderSide(color: Theme.of(context).colorScheme.error),
                ),
                child: labelWidget,
              )
            : OutlinedButton.icon(
                onPressed: handler,
                style: OutlinedButton.styleFrom(
                  foregroundColor: Theme.of(context).colorScheme.error,
                  side: BorderSide(color: Theme.of(context).colorScheme.error),
                ),
                icon: iconWidget,
                label: labelWidget,
              ),
    };
  }
}

/// Icon-only control has a compulsory human-readable tooltip and 48dp target.
/// All five main surfaces must use this instead of inventing local icon skins.
class MakoloIconActionButton extends StatelessWidget {
  const MakoloIconActionButton({
    super.key,
    required this.tooltip,
    required this.icon,
    required this.onPressed,
    this.color,
    this.phase = MakoloActionPhase.available,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;
  final Color? color;
  final MakoloActionPhase phase;

  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: switch (phase) {
      MakoloActionPhase.processing => '$tooltip · en cours',
      MakoloActionPhase.failed => '$tooltip · échec, réessayer',
      _ => tooltip,
    },
    icon: MakoloActionFeedback(phase: phase, child: Icon(icon)),
    onPressed:
        phase == MakoloActionPhase.processing ||
            phase == MakoloActionPhase.unavailable
        ? null
        : onPressed,
    color: color,
    style: IconButton.styleFrom(minimumSize: const Size(48, 48)),
  );
}

/// Visual phases of an action, never a replacement for owner-owned state.
/// A tap may start processing; only the service response confirms completion.
enum MakoloActionPhase { available, processing, confirmed, failed, unavailable }

/// Short causal feedback. The caller chooses the phase from the real result;
/// this widget never starts an operation or asserts that it succeeded.
class MakoloActionFeedback extends StatelessWidget {
  const MakoloActionFeedback({
    super.key,
    required this.phase,
    required this.child,
    this.size = 20,
  });

  final MakoloActionPhase phase;
  final Widget child;
  final double size;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final content = switch (phase) {
      MakoloActionPhase.processing => SizedBox(
        key: const ValueKey('action-processing'),
        width: size,
        height: size,
        child: CircularProgressIndicator(strokeWidth: 2, color: scheme.primary),
      ),
      MakoloActionPhase.failed => Icon(
        Icons.error_outline_rounded,
        key: const ValueKey('action-failed'),
        size: size,
        color: scheme.error,
      ),
      _ => KeyedSubtree(key: const ValueKey('action-content'), child: child),
    };
    return AnimatedSwitcher(
      duration: MakoloMotion.effective(context, MakoloMotion.short),
      switchInCurve: Curves.easeOut,
      switchOutCurve: Curves.easeIn,
      child: content,
    );
  }
}

/// Consistent empty pill around one existing N1 action.
/// An affirmed Save can be lightly tinted; opening and sharing stay unfilled.
class MakoloRoundedActionSlot extends StatelessWidget {
  const MakoloRoundedActionSlot({
    super.key,
    required this.child,
    this.active = false,
    this.phase = MakoloActionPhase.available,
  });

  final Widget child;
  final bool active;
  final MakoloActionPhase phase;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final pending = phase == MakoloActionPhase.processing;
    final failed = phase == MakoloActionPhase.failed;
    final disabled = phase == MakoloActionPhase.unavailable;
    final accent = failed ? scheme.error : scheme.primary;
    return AnimatedContainer(
      duration: MakoloMotion.effective(context, MakoloMotion.short),
      height: 48,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: failed
            ? scheme.error.withValues(alpha: 0.06)
            : (active || phase == MakoloActionPhase.confirmed)
            ? scheme.primary.withValues(alpha: 0.08)
            : Colors.transparent,
        border: Border.all(
          color: disabled
              ? scheme.outlineVariant.withValues(alpha: 0.55)
              : (active ||
                    pending ||
                    failed ||
                    phase == MakoloActionPhase.confirmed)
              ? accent.withValues(alpha: 0.5)
              : scheme.outlineVariant,
        ),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Center(child: child),
    );
  }
}

/// A relationship is visible only with a real, enabled follow callback.
/// This icon does not infer authority or a follow state from the owner's name.
class MakoloFollowIconButton extends StatelessWidget {
  const MakoloFollowIconButton({
    super.key,
    required this.followed,
    required this.onPressed,
    this.busy = false,
    this.failed = false,
  });

  final bool followed;
  final VoidCallback? onPressed;
  final bool busy;
  final bool failed;

  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: busy
        ? 'Suivi en cours…'
        : failed
        ? 'Suivi non confirmé. Réessayer'
        : followed
        ? 'Ne plus suivre'
        : 'Suivre',
    onPressed: busy ? null : onPressed,
    icon: busy
        ? const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : Icon(followed ? Icons.wifi_rounded : Icons.wifi_off_rounded),
    color: followed
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.onSurfaceVariant,
    style: IconButton.styleFrom(
      minimumSize: const Size(48, 48),
      side: failed
          ? BorderSide(color: Theme.of(context).colorScheme.error)
          : null,
      backgroundColor: failed
          ? Theme.of(context).colorScheme.error.withValues(alpha: 0.05)
          : Colors.transparent,
    ),
  );
}
