import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class BrandMoment extends StatefulWidget {
  const BrandMoment({super.key, required this.onFinished});

  final VoidCallback onFinished;

  @override
  State<BrandMoment> createState() => _BrandMomentState();
}

class _BrandMomentState extends State<BrandMoment>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  Timer? _reducedMotionTimer;
  bool _started = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 960),
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;

    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduceMotion) {
      _reducedMotionTimer = Timer(MakoloMotion.short, () {
        if (mounted) widget.onFinished();
      });
      return;
    }

    unawaited(
      _controller.forward().whenComplete(() {
        if (mounted) widget.onFinished();
      }),
    );
  }

  @override
  void dispose() {
    _reducedMotionTimer?.cancel();
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
                    final markProgress = CurvedAnimation(
                      parent: _controller,
                      curve: const Interval(
                        0.44,
                        0.92,
                        curve: Curves.easeOutCubic,
                      ),
                    ).value;

                    return SizedBox(
                      width: 240,
                      height: 240,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          CustomPaint(
                            key: const Key('brand-footsteps'),
                            size: const Size(220, 220),
                            painter: _FootstepPainter(
                              progress: _controller.value,
                            ),
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
      final localProgress = ((progress - start) / 0.28).clamp(0.0, 1.0);
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
