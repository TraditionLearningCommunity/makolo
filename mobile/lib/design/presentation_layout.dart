import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'makolo_theme.dart';

@immutable
class MakoloSplitGeometry {
  const MakoloSplitGeometry._({
    required this.split,
    required this.fieldWidth,
    required this.focusWidth,
    required this.gutter,
  });

  const MakoloSplitGeometry.single()
    : split = false,
      fieldWidth = 0,
      focusWidth = 0,
      gutter = 0;

  final bool split;
  final double fieldWidth;
  final double focusWidth;
  final double gutter;

  static MakoloSplitGeometry resolve({
    required double availableWidth,
    double fieldMin = MakoloLayout.fieldMinWidth,
    double focusMin = MakoloLayout.focusMinWidth,
    double focusPreferred = MakoloLayout.focusPreferredWidth,
    double focusMax = MakoloLayout.focusMaxWidth,
    double gutter = MakoloLayout.gutterPane,
    double? splitAt,
  }) {
    if (!MakoloLayout.canSplit(
      availableWidth: availableWidth,
      fieldMin: fieldMin,
      focusMin: focusMin,
      gutter: gutter,
      splitAt: splitAt,
    )) {
      return const MakoloSplitGeometry.single();
    }

    final maximumFocus = math.min(focusMax, availableWidth - gutter - fieldMin);
    final focusWidth = math.min(
      math.max(focusPreferred, focusMin),
      maximumFocus,
    );
    return MakoloSplitGeometry._(
      split: true,
      fieldWidth: availableWidth - gutter - focusWidth,
      focusWidth: focusWidth,
      gutter: gutter,
    );
  }
}

class MakoloContentFrame extends StatelessWidget {
  const MakoloContentFrame({
    super.key,
    required this.child,
    this.maxContentWidth,
    this.alignment = Alignment.topCenter,
  });

  final Widget child;
  final double? maxContentWidth;
  final AlignmentGeometry alignment;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final availableWidth = constraints.hasBoundedWidth
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        final edge = MakoloLayout.edgePaddingFor(availableWidth);
        final inside = math.max(0.0, availableWidth - (edge * 2));
        final width = maxContentWidth == null
            ? inside
            : math.min(inside, maxContentWidth!);
        return Align(
          alignment: alignment,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: edge),
            child: SizedBox(
              key: const Key('makolo-content-frame-body'),
              width: width,
              child: child,
            ),
          ),
        );
      },
    );
  }
}

class MakoloReadingWidth extends StatelessWidget {
  const MakoloReadingWidth({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: MakoloLayout.readingMaxWidth),
      child: child,
    ),
  );
}

class MakoloFocusPane extends StatelessWidget {
  const MakoloFocusPane({
    super.key,
    required this.child,
    this.maxWidth = MakoloLayout.focusMaxWidth,
  });

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) => ConstrainedBox(
    key: const Key('makolo-focus-pane'),
    constraints: BoxConstraints(maxWidth: maxWidth),
    child: child,
  );
}

class MakoloAdaptiveSplit extends StatelessWidget {
  const MakoloAdaptiveSplit({
    super.key,
    required this.field,
    required this.focus,
    this.narrow,
    this.splitAt,
    this.fieldMin = MakoloLayout.fieldMinWidth,
    this.focusMin = MakoloLayout.focusMinWidth,
    this.focusPreferred = MakoloLayout.focusPreferredWidth,
    this.focusMax = MakoloLayout.focusMaxWidth,
    this.gutter = MakoloLayout.gutterPane,
  });

  final Widget field;
  final Widget focus;
  final Widget? narrow;
  final double? splitAt;
  final double fieldMin;
  final double focusMin;
  final double focusPreferred;
  final double focusMax;
  final double gutter;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.hasBoundedWidth
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        final geometry = MakoloSplitGeometry.resolve(
          availableWidth: width,
          fieldMin: fieldMin,
          focusMin: focusMin,
          focusPreferred: focusPreferred,
          focusMax: focusMax,
          gutter: gutter,
          splitAt: splitAt,
        );
        if (!geometry.split) {
          return KeyedSubtree(
            key: const Key('makolo-adaptive-split-single'),
            child: narrow ?? field,
          );
        }

        return Row(
          key: const Key('makolo-adaptive-split-row'),
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: geometry.fieldWidth, child: field),
            SizedBox(width: geometry.gutter),
            SizedBox(
              width: geometry.focusWidth,
              child: MakoloFocusPane(maxWidth: focusMax, child: focus),
            ),
          ],
        );
      },
    );
  }
}

class MakoloAdaptiveGrid extends StatelessWidget {
  const MakoloAdaptiveGrid({
    super.key,
    required this.children,
    this.minUnitWidth = MakoloLayout.unitMinWidth,
    this.gutter = MakoloLayout.gutterGrid,
    this.maxColumns,
  });

  final List<Widget> children;
  final double minUnitWidth;
  final double gutter;
  final int? maxColumns;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.hasBoundedWidth
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        var columns = math.max(
          1,
          ((width + gutter) / (minUnitWidth + gutter)).floor(),
        );
        if (maxColumns != null) {
          columns = math.min(columns, math.max(1, maxColumns!));
        }
        final itemWidth = math.max(
          0.0,
          (width - (gutter * (columns - 1))) / columns,
        );

        return Wrap(
          key: const Key('makolo-adaptive-grid'),
          spacing: gutter,
          runSpacing: gutter,
          children: [
            for (final child in children)
              SizedBox(width: itemWidth, child: child),
          ],
        );
      },
    );
  }
}

class MakoloSpatialFrame extends StatelessWidget {
  const MakoloSpatialFrame({
    super.key,
    required this.spatial,
    this.compactFallback,
    this.minSpatialWidth = MakoloLayout.mapMinWidth,
  });

  final Widget spatial;
  final Widget? compactFallback;
  final double minSpatialWidth;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.hasBoundedWidth
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        if (width < minSpatialWidth && compactFallback != null) {
          return KeyedSubtree(
            key: const Key('makolo-spatial-compact-fallback'),
            child: compactFallback!,
          );
        }
        return KeyedSubtree(
          key: const Key('makolo-spatial-content'),
          child: spatial,
        );
      },
    );
  }
}
