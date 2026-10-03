import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';
import '../../design/presentation_media.dart';

abstract final class FixtureMediaResolver {
  static bool supports(String reference) => reference.startsWith('fixture://');

  static Widget resolve(String reference) {
    if (!supports(reference)) {
      throw ArgumentError.value(
        reference,
        'reference',
        'Only fixture:// media is allowed in Presentation scenarios.',
      );
    }
    final label = reference
        .substring('fixture://'.length)
        .replaceAll('/', ' · ');
    return MakoloMediaPlaceholder(label: label);
  }
}

class FixtureSpatialCanvas extends StatelessWidget {
  const FixtureSpatialCanvas({
    super.key,
    this.semanticLabel = 'Carte de démonstration',
  });

  final String semanticLabel;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      image: true,
      label: semanticLabel,
      child: ExcludeSemantics(
        child: CustomPaint(
          painter: _FixtureSpatialPainter(
            line: Theme.of(context).colorScheme.outlineVariant,
            marker: Theme.of(context).colorScheme.primary,
            background: context.makoloSurfaces.low,
          ),
          child: const SizedBox.expand(),
        ),
      ),
    );
  }
}

class _FixtureSpatialPainter extends CustomPainter {
  const _FixtureSpatialPainter({
    required this.line,
    required this.marker,
    required this.background,
  });

  final Color line;
  final Color marker;
  final Color background;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = background);
    final linePaint = Paint()
      ..color = line
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    final markerPaint = Paint()..color = marker;

    for (var index = 1; index < 5; index += 1) {
      final x = size.width * index / 5;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), linePaint);
    }
    for (var index = 1; index < 4; index += 1) {
      final y = size.height * index / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), linePaint);
    }

    canvas.drawCircle(
      Offset(size.width * 0.38, size.height * 0.58),
      7,
      markerPaint,
    );
    canvas.drawCircle(
      Offset(size.width * 0.66, size.height * 0.34),
      5,
      markerPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _FixtureSpatialPainter oldDelegate) =>
      oldDelegate.line != line ||
      oldDelegate.marker != marker ||
      oldDelegate.background != background;
}
