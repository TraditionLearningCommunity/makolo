import 'package:flutter/material.dart';

import '../../navigation/refresh_boundary.dart';
import '../../repositories/personal_repository.dart';
import '../personal/projection_screen.dart';

class OngoingScreen extends StatelessWidget {
  const OngoingScreen({super.key, required this.repository});

  final PersonalRepository repository;

  @override
  Widget build(BuildContext context) => MakoloRefreshBoundary(
    child: ProjectionScreen(
      title: 'En cours',
      stream: repository.watchOngoing(),
      emptyMessage: 'Aucun engagement en cours.',
      showTitle: false,
    ),
  );
}
