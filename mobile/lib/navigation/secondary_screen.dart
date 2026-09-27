import 'package:flutter/material.dart';

import '../design/behavior_states.dart';
import '../design/makolo_theme.dart';
import 'shell_header.dart';

class MakoloSecondaryScreen extends StatelessWidget {
  const MakoloSecondaryScreen({
    super.key,
    required this.title,
    required this.message,
    this.actions = const [],
  });

  final String title;
  final String message;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: MakoloSecondaryHeader(title: title, actions: actions),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          children: [InlineMessage(message: message)],
        ),
      ),
    );
  }
}
