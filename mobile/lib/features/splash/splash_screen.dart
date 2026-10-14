import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: MakoloColors.indigo,
      // Same centered final artwork as the Android splash, with no replay.
      body: Center(child: MakoloMark(size: 78, white: true)),
    );
  }
}
