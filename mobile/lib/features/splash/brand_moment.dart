import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class BrandMoment extends StatefulWidget {
  const BrandMoment({super.key, this.onFinished, this.startedAt});

  final VoidCallback? onFinished;

  // Conservé pour compatibilité avec LaunchGate.
  // L'animation ne saute plus des images en fonction de cette date.
  final DateTime? startedAt;

  @override
  State<BrandMoment> createState() => _BrandMomentState();
}

class _BrandMomentState extends State<BrandMoment>
    with SingleTickerProviderStateMixin {
  static const duration = Duration(milliseconds: 1200);

  late final AnimationController _controller;

  bool _started = false;
  bool _finished = false;

  @override
  void initState() {
    super.initState();

    _controller = AnimationController(vsync: this, duration: duration);

    _controller.addStatusListener(_onAnimationStatusChanged);
  }

  void _onAnimationStatusChanged(AnimationStatus status) {
    if (status == AnimationStatus.completed) {
      _notifyFinished();
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    if (_started) return;
    _started = true;

    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;

    if (reduceMotion) {
      _controller.value = 1;
      _notifyFinished();
      return;
    }

    // L'horloge commence lorsque le widget entre réellement
    // dans l'arbre Flutter, pas au démarrage du processus Android.
    //
    // Une ancienne valeur startedAt ne doit donc jamais
    // raccourcir ou supprimer l'animation.
    _controller.forward(from: 0);
  }

  void _notifyFinished() {
    if (_finished) return;
    _finished = true;

    // Ne pas modifier LaunchGate pendant la construction
    // de son arbre de widgets.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      widget.onFinished?.call();
    });
  }

  @override
  void dispose() {
    _controller.removeStatusListener(_onAnimationStatusChanged);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;

    return Scaffold(
      backgroundColor: MakoloColors.indigo,
      body: SafeArea(
        child: Center(
          child: reduceMotion
              ? const MakoloMark(size: 78, white: true)
              : AnimatedBuilder(
                  animation: _controller,
                  builder: (context, child) {
                    final progress = _controller.value;

                    // Les pas apparaissent progressivement.
                    // Le Mark se révèle pendant la seconde
                    // partie de la séquence.
                    final markProgress = Curves.easeOutCubic.transform(
                      ((progress - 0.44) / 0.48).clamp(0.0, 1.0).toDouble(),
                    );

                    return SizedBox(
                      width: 240,
                      height: 240,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          CustomPaint(
                            key: const Key('brand-footsteps'),
                            size: const Size(220, 220),
                            painter: _FootstepPainter(progress: progress),
                          ),
                          Opacity(
                            opacity: markProgress,
                            child: Transform.scale(
                              scale: 0.92 + (0.08 * markProgress),
                              child: const MakoloMark(size: 78, white: true),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
        ),
      ),
    );
  }
}

class _FootstepPainter extends CustomPainter {
  const _FootstepPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = MakoloColors.warm;

    final centers = <Offset>[
      Offset(size.width * 0.34, size.height * 0.66),
      Offset(size.width * 0.50, size.height * 0.52),
      Offset(size.width * 0.63, size.height * 0.37),
    ];

    final rotations = <double>[-0.22, 0.16, -0.12];

    for (var index = 0; index < centers.length; index++) {
      final start = index * 0.13;

      final localProgress = ((progress - start) / 0.28)
          .clamp(0.0, 1.0)
          .toDouble();

      if (localProgress <= 0) continue;

      paint.color = MakoloColors.warm.withValues(
        alpha: 0.18 + (0.64 * localProgress),
      );

      canvas.save();

      canvas.translate(centers[index].dx, centers[index].dy);

      canvas.rotate(rotations[index] * math.pi);

      canvas.drawRRect(
        RRect.fromRectAndRadius(
          const Rect.fromLTWH(-8, -17, 16, 34),
          const Radius.circular(10),
        ),
        paint,
      );

      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant _FootstepPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}
