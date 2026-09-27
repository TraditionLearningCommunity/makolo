import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) => const Scaffold(
    body: SafeArea(child: Center(child: MakoloMark(size: 72))),
  );
}
