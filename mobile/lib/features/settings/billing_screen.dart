import 'package:flutter/material.dart';

import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';

class BillingScreen extends StatelessWidget {
  const BillingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Abonnement & facturation')),
      body: const MakoloContentFrame(
        child: ListView(
          padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
          children: [
            MakoloSection(
              title: 'Abonnement & facturation',
              description:
                  'Aucune information d’abonnement ou de facturation n’est '
                  'disponible dans Makolo pour le moment.',
              child: MakoloCard(
                child: Text(
                  'Aucun plan, prix, moyen de paiement ou historique de '
                  'transaction n’est affiché tant qu’une capacité réelle ne '
                  'les fournit pas.',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
