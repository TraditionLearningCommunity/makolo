import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 960),
    )..repeat();
  }

  @override
  void dispose() {
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
                    final pulse = Curves.easeInOut.transform(
                      0.5 - (0.5 * math.cos(_controller.value * math.pi)),
                    );
                    return SizedBox(
                      width: 220,
                      height: 220,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          CustomPaint(
                            key: const Key('splash-footsteps'),
                            size: const Size(190, 190),
                            painter: _SplashFootstepPainter(
                              progress: _controller.value,
                            ),
                          ),
                          Transform.translate(
                            offset: Offset(0, -1.5 * pulse),
                            child: const MakoloMark(size: 78, white: true),
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

class _SplashFootstepPainter extends CustomPainter {
  const _SplashFootstepPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint();
    final centers = <Offset>[
      Offset(size.width * 0.43, size.height * 0.63),
      Offset(size.width * 0.56, size.height * 0.57),
    ];

    for (var index = 0; index < centers.length; index++) {
      final phase = (progress + (index * 0.5)) % 1.0;
      final visibility = math.sin(phase * math.pi).clamp(0.0, 1.0);
      if (visibility <= 0.05) continue;

      paint.color = MakoloColors.warm.withValues(
        alpha: 0.16 + (0.42 * visibility),
      );
      canvas.save();
      canvas.translate(centers[index].dx, centers[index].dy);
      canvas.rotate((index.isEven ? -0.08 : 0.08) * math.pi);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          const Rect.fromLTWH(-5, -11, 10, 22),
          const Radius.circular(7),
        ),
        paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant _SplashFootstepPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}
