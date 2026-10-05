import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/presentation_layout.dart';

class BillingScreen extends StatelessWidget {
  const BillingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Abonnement & facturation')),
      body: const MakoloContentFrame(
        child: MakoloEmptyState(
          title: 'Aucun abonnement ou élément de facturation pour le moment.',
          icon: Icons.receipt_long_outlined,
        ),
      ),
    );
  }
}
