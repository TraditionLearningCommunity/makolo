import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

SystemUiOverlayStyle makoloSystemUiStyle(BuildContext context) {
  final dark = Theme.of(context).brightness == Brightness.dark;
  return SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    systemNavigationBarColor: Colors.transparent,
    systemNavigationBarDividerColor: Colors.transparent,
    statusBarIconBrightness: dark ? Brightness.light : Brightness.dark,
    systemNavigationBarIconBrightness: dark
        ? Brightness.light
        : Brightness.dark,
    statusBarBrightness: dark ? Brightness.dark : Brightness.light,
    systemStatusBarContrastEnforced: false,
    systemNavigationBarContrastEnforced: false,
  );
}

class MakoloSystemUi extends StatelessWidget {
  const MakoloSystemUi({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: makoloSystemUiStyle(context),
      child: child,
    );
  }
}
