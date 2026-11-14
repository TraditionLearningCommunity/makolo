import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../presentation/contracts/space_presentation.dart';

/// MT5 owner-backed Commerce / Transport depth. Every navigation re-reads
/// Work under the active Space actor and its current responsibility.
class SpaceWorkG3Depth extends StatelessWidget {
  const SpaceWorkG3Depth({
    super.key,
    required this.slug,
    required this.payload,
    this.ownerId,
    required this.onPageChange,
    required this.onSecondaryPageChange,
    this.workSection,
    this.fromWorkCollection = false,
  });

  final String slug;
  final Map<String, dynamic> payload;
  final String? ownerId;
  final ValueChanged<int> onPageChange;
  final ValueChanged<int> onSecondaryPageChange;
  final String? workSection;
  final bool fromWorkCollection;

  @override
  Widget build(BuildContext context) {
    final kind = spaceText(payload['kind']);
    final facts = spaceMap(payload['facts']) ?? const <String, dynamic>{};
    final widgets = <Widget>[];
    if (kind == 'commerce_activity') {
      widgets.add(_heading(context, 'Offres de cette activité'));
      if (facts['can_manage_offer'] == true && ownerId != null) {
        widgets.add(
          MakoloActionButton(
            appearance: MakoloActionAppearance.primary,
            icon: Icons.add,
            label: 'Créer une offre',
            onPressed: () => context.push(
              '/space/${Uri.encodeComponent(slug)}/work/g3/'
              'activities/${Uri.encodeComponent(ownerId!)}/offers/new',
            ),
          ),
        );
      }
    } else if (kind == 'offer') {
      widgets.add(_heading(context, 'Conditions de cette offre'));
      if (facts['can_manage_offer'] == true && ownerId != null) {
        widgets.add(
          MakoloActionButton(
            appearance: MakoloActionAppearance.primary,
            icon: Icons.edit_outlined,
            label: 'Modifier l’offre',
            onPressed: () => context.push(
              '/space/${Uri.encodeComponent(slug)}/work/g3/'
              'offers/${Uri.encodeComponent(ownerId!)}/edit',
            ),
          ),
        );
      }
      widgets.add(
        _fact('Prix unitaire', _money(facts['unit_price'], facts['currency'])),
      );
      widgets.add(
        _fact(
          'Mode de paiement',
          spaceText(facts['payment_mode']) ?? 'Non établi',
        ),
      );
      widgets.add(
        _fact(
          'Quantité par demande',
          '${facts['min_quantity']}'
              '${facts['max_quantity'] == null ? ' minimum' : ' à ${facts['max_quantity']}'}',
        ),
      );
      widgets.add(
        _fact(
          'Disponibilité maintenant',
          facts['currently_available'] == true
              ? 'Disponible'
              : 'Non disponible',
        ),
      );
      if (facts['available_from'] != null) {
        widgets.add(_fact('À partir du', facts['available_from'].toString()));
      }
      if (facts['available_until'] != null) {
        widgets.add(_fact('Jusqu’au', facts['available_until'].toString()));
      }
      if (facts['capacity_pool_bound'] == true) {
        widgets.add(
          const Text(
            'La quantité disponible dépend des réservations et engagements en cours.',
          ),
        );
      }
    } else if (kind == 'commerce_order') {
      widgets.add(_heading(context, 'Commande ${facts['reference'] ?? ''}'));
      widgets.add(
        _fact(
          'Sous-total historique',
          _money(facts['subtotal'], facts['currency']),
        ),
      );
      widgets.add(
        _fact(
          'Remise historique',
          _money(facts['discount_total'], facts['currency']),
        ),
      );
      widgets.add(
        _fact('Total commandé', _money(facts['total'], facts['currency'])),
      );
      widgets.add(
        _fact(
          'Paiement prévu',
          spaceText(facts['payment_mode']) ?? 'Non établi',
        ),
      );
      widgets.add(
        const Text(
          'Une commande confirmée ne confirme ni le paiement ni la remise.',
        ),
      );
    } else if (kind == 'transport_route') {
      widgets.add(_heading(context, 'Route de transport'));
      if (spaceText(facts['code']) case final String code) {
        widgets.add(_fact('Code', code));
      }
      widgets.add(
        _fact('État', facts['active'] == true ? 'Active' : 'Inactive'),
      );
    } else if (kind == 'vehicle') {
      widgets.add(_heading(context, 'Véhicule'));
      widgets.add(
        _fact('Type', spaceText(facts['vehicle_type']) ?? 'Non établi'),
      );
      if (facts['passenger_capacity'] is num) {
        widgets.add(
          _fact('Places physiques', '${facts['passenger_capacity']}'),
        );
      }
      if (spaceText(facts['registration']) case final String registration) {
        widgets.add(_fact('Immatriculation', registration));
      }
      widgets.add(
        const Text(
          'La capacité du véhicule ne correspond pas forcément aux places à vendre.',
        ),
      );
    } else if (kind == 'transport_service') {
      widgets.add(_heading(context, 'Service de transport'));
      final route = spaceMap(facts['route']);
      if (spaceText(route?['name']) case final String name) {
        widgets.add(_fact('Itinéraire', name));
      }
      if (spaceText(facts['mode']) case final String mode) {
        widgets.add(_fact('Mode', mode));
      }
    } else if (kind == 'transport_departure') {
      widgets.add(_heading(context, 'Départ réel'));
      final departureId = spaceText(facts['departure_id']);
      if (facts['can_manage_operations'] == true && departureId != null) {
        widgets.add(
          MakoloActionButton(
            appearance: MakoloActionAppearance.primary,
            icon: Icons.tune_outlined,
            label: 'Exploiter ce départ',
            onPressed: () => context.push(
              '/space/${Uri.encodeComponent(slug)}/work/g3/'
              'departures/${Uri.encodeComponent(departureId)}/operate',
            ),
          ),
        );
      }
      final route = spaceMap(facts['route']);
      if (spaceText(route?['name']) case final String name) {
        widgets.add(_fact('Itinéraire', name));
      }
      if (facts['vehicle_assignment_known'] == true) {
        final vehicle = spaceMap(facts['vehicle']);
        if (vehicle == null) {
          widgets.add(_fact('Véhicule', 'Non affecté'));
        } else {
          widgets.add(
            _fact(
              'Véhicule',
              '${spaceText(vehicle['label']) ?? 'Véhicule'} · '
                  '${vehicle['physical_capacity']} places physiques',
            ),
          );
        }
      }
      if (spaceText(facts['boarding_instructions'])
          case final String instructions) {
        widgets.add(_fact('Embarquement', instructions));
      }
      widgets.add(
        const Text(
          'Le nombre de places disponibles ne confirme pas la présence des voyageurs.',
        ),
      );
    }
    for (final key in ['offers', 'lines', 'services', 'departures']) {
      final list = spaceMap(payload[key]);
      if (list != null) {
        widgets.add(
          _collection(
            context,
            key: key,
            data: list,
            onChange: key == 'departures' && kind == 'transport_route'
                ? onSecondaryPageChange
                : onPageChange,
          ),
        );
      }
    }
    return Padding(
      padding: const EdgeInsets.only(top: 18, bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final widget in widgets) ...[widget, const SizedBox(height: 12)],
        ],
      ),
    );
  }

  Widget _heading(BuildContext context, String title) =>
      Text(title, style: Theme.of(context).textTheme.titleMedium);

  Widget _fact(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Text('$label : $value'),
  );

  String _money(dynamic amount, dynamic currency) =>
      '${amount ?? '—'} ${currency ?? ''}'.trim();

  Widget _collection(
    BuildContext context, {
    required String key,
    required Map<String, dynamic> data,
    required ValueChanged<int> onChange,
  }) {
    final items = data['items'] is List ? data['items'] as List : const [];
    final offset = data['offset'] is int ? data['offset'] as int : 0;
    final limit = data['limit'] is int ? data['limit'] as int : 12;
    final hasMore = data['has_more'] == true;
    final label = switch (key) {
      'offers' => 'Offres liées',
      'lines' => 'Lignes de commande',
      'services' => 'Services de cette route',
      _ => 'Départs liés',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _heading(context, label),
        if (items.isEmpty)
          const Text('Aucun élément visible dans cette sélection.'),
        for (final raw in items)
          if (spaceMap(raw) case final Map<String, dynamic> item)
            _row(context, item, key),
        if (offset > 0 || hasMore)
          Wrap(
            spacing: 8,
            children: [
              if (offset > 0)
                MakoloActionButton(
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: () =>
                      onChange(offset > limit ? offset - limit : 0),
                  label: 'Précédents',
                ),
              if (hasMore)
                MakoloActionButton(
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: () => onChange(offset + limit),
                  label: 'Voir les suivants',
                ),
            ],
          ),
      ],
    );
  }

  Widget _row(
    BuildContext context,
    Map<String, dynamic> item,
    String collection,
  ) {
    final source = spaceMap(item['source']);
    final route = collection == 'lines' || item['openable'] == false
        ? null
        : spaceWorkOwnerRoute(
            slug: slug,
            kind: spaceText(source?['kind']),
            id: spaceText(source?['id']),
            section: workSection,
            fromCollection: fromWorkCollection,
          );
    final timing = spaceMap(item['timing']);
    final label =
        spaceText(item['label']) ?? spaceText(item['title']) ?? 'Élément réel';
    final info = [
      if (item['quantity'] is num) '${item['quantity']} unité(s)',
      if (item['line_total'] != null)
        _money(item['line_total'], item['currency']),
      if (timing?['start_date'] != null) '${timing?['start_date']}',
      if (spaceText(item['state']) case final String state)
        spaceStateLabel(state),
    ].join(' · ');
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      subtitle: Text(info),
      trailing: route != null ? const Icon(Icons.chevron_right) : null,
      onTap: route == null ? null : () => context.push(route),
    );
  }
}
