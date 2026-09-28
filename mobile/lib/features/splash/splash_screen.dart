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
      duration: const Duration(milliseconds: 920),
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
                    final phase = _controller.value * math.pi * 2;
                    final vertical = -1.6 * math.sin(phase).abs();
                    final horizontal = 1.1 * math.sin(phase);
                    final rotation = 0.012 * math.sin(phase);

                    return Transform.translate(
                      key: const Key('animated-splash-mark'),
                      offset: Offset(horizontal, vertical),
                      child: Transform.rotate(
                        angle: rotation,
                        child: const MakoloMark(size: 78, white: true),
                      ),
                    );
                  },
                ),
        ),
      ),
    );
  }
}
