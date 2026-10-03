import 'package:flutter/material.dart';

import 'makolo_theme.dart';

enum MakoloMediaAspect { square, standard, landscape, document, fluid }

extension MakoloMediaAspectRatio on MakoloMediaAspect {
  double? get value => switch (this) {
    MakoloMediaAspect.square => 1,
    MakoloMediaAspect.standard => 4 / 3,
    MakoloMediaAspect.landscape => 16 / 9,
    MakoloMediaAspect.document => 3 / 4,
    MakoloMediaAspect.fluid => null,
  };
}

class MakoloMediaFrame extends StatelessWidget {
  const MakoloMediaFrame({
    super.key,
    required this.aspect,
    this.child,
    this.placeholder,
    this.semanticLabel,
    this.radius = MakoloRadii.card,
  });

  final MakoloMediaAspect aspect;
  final Widget? child;
  final Widget? placeholder;
  final String? semanticLabel;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final media = ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child:
          child ??
          placeholder ??
          const MakoloMediaPlaceholder(),
    );
    final framed = aspect.value == null
        ? media
        : AspectRatio(aspectRatio: aspect.value!, child: media);
    if (semanticLabel == null) {
      return ExcludeSemantics(child: framed);
    }
    return Semantics(image: true, label: semanticLabel, child: framed);
  }
}

class MakoloMediaPlaceholder extends StatelessWidget {
  const MakoloMediaPlaceholder({
    super.key,
    this.label,
    this.icon = Icons.image_outlined,
  });

  final String? label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final foreground = Theme.of(context).colorScheme.onSurfaceVariant;
    return ColoredBox(
      color: context.makoloSurfaces.low,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.md),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: foreground),
              if (label != null) ...[
                const SizedBox(height: MakoloSpacing.sm),
                Text(
                  label!,
                  textAlign: TextAlign.center,
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: foreground),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
