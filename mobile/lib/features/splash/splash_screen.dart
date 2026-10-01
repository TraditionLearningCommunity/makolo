import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: MakoloColors.indigo,
      body: SafeArea(
        child: Center(
          child: MakoloMark(size: 78, white: true),
        ),
      ),
    );
  }
}
