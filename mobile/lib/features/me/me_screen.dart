import 'package:flutter/material.dart';

import '../../navigation/refresh_boundary.dart';
import '../../repositories/personal_repository.dart';
import '../personal/projection_screen.dart';

class MeScreen extends StatelessWidget {
  const MeScreen({super.key, required this.repository});

  final PersonalRepository repository;

  @override
  Widget build(BuildContext context) => MakoloRefreshBoundary(
    child: ProjectionScreen(
      title: 'Moi',
      stream: repository.watchMe(),
      emptyMessage: 'Aucune information à afficher pour le moment.',
      showTitle: false,
    ),
  );
}
