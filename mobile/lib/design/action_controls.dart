import 'package:flutter/material.dart';

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
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final MakoloActionAppearance appearance;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final handler = busy ? null : onPressed;
    final visibleIcon = busy && icon != null
        ? Icons.hourglass_top_rounded
        : icon;
    final labelWidget = Text(label);
    return switch (appearance) {
      MakoloActionAppearance.primary =>
        visibleIcon == null
            ? FilledButton(onPressed: handler, child: labelWidget)
            : FilledButton.icon(
                onPressed: handler,
                icon: Icon(visibleIcon),
                label: labelWidget,
              ),
      MakoloActionAppearance.secondary =>
        visibleIcon == null
            ? OutlinedButton(onPressed: handler, child: labelWidget)
            : OutlinedButton.icon(
                onPressed: handler,
                icon: Icon(visibleIcon),
                label: labelWidget,
              ),
      MakoloActionAppearance.quiet =>
        visibleIcon == null
            ? TextButton(onPressed: handler, child: labelWidget)
            : TextButton.icon(
                onPressed: handler,
                icon: Icon(visibleIcon),
                label: labelWidget,
              ),
      MakoloActionAppearance.danger =>
        visibleIcon == null
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
                icon: Icon(visibleIcon),
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
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;
  final Color? color;

  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: tooltip,
    icon: Icon(icon),
    onPressed: onPressed,
    color: color,
    style: IconButton.styleFrom(minimumSize: const Size(48, 48)),
  );
}

 
/// Consistent empty pill around one existing N1 action.
/// An affirmed Save can be lightly tinted; opening and sharing stay unfilled.
class MakoloRoundedActionSlot extends StatelessWidget {
  const MakoloRoundedActionSlot({
    super.key,
    required this.child,
    this.active = false,
  });

  final Widget child;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      height: 48,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: active
            ? scheme.primary.withValues(alpha: 0.08)
            : Colors.transparent,
        border: Border.all(
          color: active
              ? scheme.primary.withValues(alpha: 0.48)
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
  });

  final bool followed;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: followed ? 'Ne plus suivre' : 'Suivre',
    onPressed: onPressed,
    icon: Icon(followed ? Icons.wifi_rounded : Icons.wifi_outlined),
    color: followed
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.onSurfaceVariant,
    style: IconButton.styleFrom(minimumSize: const Size(48, 48)),
  );
}
