import 'package:flutter/material.dart';

import '../../navigation/refresh_boundary.dart';
import '../../repositories/personal_repository.dart';
import '../personal/projection_screen.dart';

class NowScreen extends StatelessWidget {
  const NowScreen({super.key, required this.repository});

  final PersonalRepository repository;

  @override
  Widget build(BuildContext context) => MakoloRefreshBoundary(
    child: ProjectionScreen(
      title: 'Now',
      stream: repository.watchNow(),
      emptyMessage: 'Tout est en ordre. ✓',
      showTitle: false,
    ),
  );
}
