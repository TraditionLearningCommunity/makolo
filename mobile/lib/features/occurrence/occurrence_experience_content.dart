import 'package:flutter/material.dart';

import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';

/// A single renderer for Jour J / Makolo Live, independent of Profile/Space
/// navigation. The server owns which sections and actions can be displayed.
class OccurrenceExperienceContent extends StatelessWidget {
  const OccurrenceExperienceContent({
    super.key,
    required this.payload,
    required this.live,
    this.remoteActionsAvailable = true,
    this.onOpenAccess,
    this.onPresentCredential,
    this.onOpenLive,
    this.onOpenScanner,
    this.onBackToDayOf,
  });

  final Map<String, dynamic> payload;
  final bool live;
  final bool remoteActionsAvailable;
  final void Function(String accessId, String path)? onOpenAccess;
  final void Function(String accessId, String path)? onPresentCredential;
  final ValueChanged<String>? onOpenLive;
  final VoidCallback? onOpenScanner;
  final VoidCallback? onBackToDayOf;

  static Map<String, dynamic> _map(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

  static List<Map<String, dynamic>> _rows(Object? value) => value is List
      ? value.whereType<Map>().map((value) => _map(value)).toList()
      : const [];

  static String? _text(Object? value) {
    final valueText = value?.toString().trim();
    return valueText == null || valueText.isEmpty ? null : valueText;
  }

  static String _phase(String? phase) => switch (phase) {
    'before' => 'À préparer',
    'arrival' => 'Accueil / arrivée',
    'live' => 'En cours',
    'after' => 'Terminé',
    'cancelled' => 'Annulé',
    _ => 'Situation à confirmer',
  };

  static String _truth(String? truth) => switch (truth) {
    'planned' => 'Prévu',
    'estimated' => 'Estimé',
    'observed' => 'Observé',
    'live' => 'Observé actuellement',
    'unknown' => 'Inconnu',
    'unavailable' => 'Indisponible',
    _ => 'À vérifier',
  };

  static String _value(Object? value) {
    if (value == null) return 'Non renseigné';
    if (value is Map) {
      final entries = value.entries
          .where((entry) => entry.value != null)
          .map((entry) => '${entry.key} : ${_value(entry.value)}');
      return entries.isEmpty ? 'Non renseigné' : entries.join(' · ');
    }
    if (value is List) return value.map(_value).join(', ');
    if (value is bool) return value ? 'Oui' : 'Non';
    return value.toString();
  }

  static String _capabilityLabel(String capability) => switch (capability) {
    'scanner' => 'Scanner',
    'finance_view' => 'Consulter les finances',
    'finance_manage' => 'Gérer les finances',
    'operations_view' => 'Consulter les opérations',
    'operations_manage' => 'Gérer les opérations',
    'capacity_view' => 'Consulter la capacité',
    'capacity_manage' => 'Gérer la capacité',
    'commerce_view' => 'Consulter le commerce',
    'commerce_manage' => 'Gérer le commerce',
    'access_control_view' => 'Contrôler les accès',
    'access_control_manage' => 'Gérer les accès',
    'place_view' => 'Consulter les lieux',
    'place_manage' => 'Gérer les lieux',
    'institutional_journey_view' => 'Démarche de mon Espace',
    _ => capability.replaceAll('_', ' '),
  };

  @override
  Widget build(BuildContext context) {
    final contextData = _map(payload['context']);
    final activity = _map(contextData['activity']);
    final occurrence = _map(contextData['occurrence']);
    final title = _text(occurrence['label']) ??
        _text(activity['title']) ??
        'Occurrence';
    return ListView(
      key: Key(live ? 'canonical-live-content' : 'canonical-day-of-content'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        if (live && onBackToDayOf != null)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: onBackToDayOf,
              icon: const Icon(Icons.arrow_back_rounded),
              label: const Text('Retour au Jour J'),
            ),
          ),
        Text(title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: MakoloSpacing.xs),
        Text(
          '${_text(activity['title']) ?? ''} · ${_phase(_text(payload['phase']))}',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: MakoloSpacing.lg),
        if (live) ..._liveSections(context) else ..._dayOfSections(context),
      ],
    );
  }

  List<Widget> _dayOfSections(BuildContext context) {
    final sections = _map(payload['sections']);
    final participant = _map(sections['participant']);
    final operator = _map(sections['organizer']);
    final platform = _map(sections['platform']);
    final institutional = _rows(sections['institutional']);
    final actions = _rows(payload['actions']);
    final knowledge = _map(payload['knowledge']);
    final coverage = _map(knowledge['coverage']);
    final links = _map(payload['links']);
    final liveStatus = _map(payload['live']);
    final capabilities = _map(payload['capabilities']);

    return [
      if (actions.isNotEmpty) ...[
        MakoloSection(
          title: 'À faire maintenant',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final action in actions) ...[
                MakoloCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        switch (_text(action['territory'])) {
                          'participant' => 'Mon accomplissement',
                          'organizer' => 'Organisation',
                          'platform' => 'Supervision',
                          _ => 'Action autorisée',
                        },
                        style: Theme.of(context).textTheme.labelMedium,
                      ),
                      const SizedBox(height: MakoloSpacing.xs),
                      Text(
                        _text(action['label']) ?? 'Action à vérifier',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      if (action['kind'] == 'owner_handoff' &&
                          action['type'] == 'scanner' &&
                          capabilities.containsKey('scanner') &&
                          onOpenScanner != null) ...[
                        const SizedBox(height: MakoloSpacing.md),
                        FilledButton.icon(
                          onPressed: remoteActionsAvailable
                              ? onOpenScanner
                              : null,
                          icon: const Icon(Icons.qr_code_scanner_rounded),
                          label: const Text('Ouvrir Scanner'),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: MakoloSpacing.sm),
              ],
            ],
          ),
        ),
        const SizedBox(height: MakoloSpacing.lg),
      ],
      if (participant.isNotEmpty) ...[
        MakoloSection(
          title: 'Mon accomplissement',
          child: _participantSection(context, participant),
        ),
        const SizedBox(height: MakoloSpacing.lg),
      ],
      if (institutional.isNotEmpty) ...[
        MakoloSection(
          title: 'Démarches de mon Espace',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final journey in institutional)
                Padding(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                  child: MakoloCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _text(_map(journey['beneficiary'])['name']) ??
                              'Espace',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          '${_text(journey['workflow']) ?? 'Démarche'} · ${_text(journey['status']) ?? 'À vérifier'}',
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: MakoloSpacing.lg),
      ],
      if (operator.isNotEmpty || platform.isNotEmpty) ...[
        MakoloSection(
          title: operator.isNotEmpty
              ? 'Conduite de l’Occurrence'
              : 'Supervision autorisée',
          child: _operatorSection(context, operator.isNotEmpty ? operator : platform),
        ),
        const SizedBox(height: MakoloSpacing.lg),
      ],
      if (capabilities.isNotEmpty) ...[
        MakoloSection(
          title: 'Mes autres responsabilités',
          child: MakoloCard(
            child: Wrap(
              spacing: MakoloSpacing.sm,
              runSpacing: MakoloSpacing.sm,
              children: [
                for (final capability in capabilities.keys)
                  Chip(label: Text(_capabilityLabel(capability))),
              ],
            ),
          ),
        ),
        const SizedBox(height: MakoloSpacing.lg),
      ],
      if (liveStatus['available'] == true &&
          links['live'] is String &&
          onOpenLive != null) ...[
        MakoloSection(
          title: 'Suivi de la situation',
          child: MakoloCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  coverage['state'] == 'PARTIAL'
                      ? 'Des faits sont disponibles, mais leur couverture reste partielle.'
                      : 'Consulter les observations disponibles.',
                ),
                const SizedBox(height: MakoloSpacing.md),
                FilledButton.icon(
                  onPressed: remoteActionsAvailable
                      ? () => onOpenLive!(_text(links['live'])!)
                      : null,
                  icon: const Icon(Icons.visibility_outlined),
                  label: const Text('Consulter Makolo Live'),
                ),
              ],
            ),
          ),
        ),
      ],
    ];
  }

  Widget _participantSection(
    BuildContext context,
    Map<String, dynamic> participant,
  ) {
    final accesses = _rows(participant['access']);
    final queue = _rows(participant['queue']);
    final placements = _rows(participant['placement']);
    final spatial = _map(participant['spatial']);
    final destination = _map(spatial['destination']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (destination.isNotEmpty)
          MakoloCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Destination prévue'),
                Text(
                  [
                    _text(destination['name']),
                    _text(destination['address_line']),
                    _text(destination['locality']),
                  ].whereType<String>().join(' · '),
                ),
              ],
            ),
          ),
        for (final access in accesses) ...[
          const SizedBox(height: MakoloSpacing.sm),
          MakoloCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Mon accès · ${_text(access['state']) ?? 'à vérifier'}'),
                Text(access['usable'] == true
                    ? 'Utilisable selon ses conditions'
                    : 'État d’utilisation à vérifier'),
                if (_map(access['credential'])['presentable'] == true &&
                    _text(_map(access['links'])['credential']) != null &&
                    onPresentCredential != null) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  FilledButton.icon(
                    onPressed: () => onPresentCredential!(
                      _text(_map(access['identity'])['id']) ?? '',
                      _text(_map(access['links'])['credential'])!,
                    ),
                    icon: const Icon(Icons.qr_code_2_rounded),
                    label: const Text('Présenter mon accès'),
                  ),
                ],
                if (_text(_map(access['links'])['detail']) != null &&
                    onOpenAccess != null) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  OutlinedButton(
                    onPressed: () => onOpenAccess!(
                      _text(_map(access['identity'])['id']) ?? '',
                      _text(_map(access['links'])['detail'])!,
                    ),
                    child: const Text('Détail du droit'),
                  ),
                ],
              ],
            ),
          ),
        ],
        for (final item in queue) ...[
          const SizedBox(height: MakoloSpacing.sm),
          MakoloCard(
            child: Text(
              'Ma file : ${_text(item['label']) ?? 'File'} · ${_text(item['state']) ?? 'à vérifier'}'
              '${item['position'] == null ? '' : ' · Position ${item['position']}'}',
            ),
          ),
        ],
        for (final placement in placements) ...[
          const SizedBox(height: MakoloSpacing.sm),
          MakoloCard(
            child: Text(
              'Mon placement : ${_text(placement['unit']) ?? 'à vérifier'}',
            ),
          ),
        ],
      ],
    );
  }

  Widget _operatorSection(
    BuildContext context,
    Map<String, dynamic> operator,
  ) {
    final readiness = _map(operator['operational_readiness']);
    final queue = _rows(operator['queue']);
    final capacity = _rows(operator['capacity']);
    final checkpoints = _rows(operator['checkpoints']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        MakoloCard(
          child: Text(
            'Préparation : ${_text(readiness['state']) ?? 'non renseignée'}',
          ),
        ),
        for (final item in queue) ...[
          const SizedBox(height: MakoloSpacing.sm),
          MakoloCard(
            child: Text(
              'File ${_text(item['label']) ?? ''} · ${_text(item['status']) ?? 'à vérifier'}'
              '${item['counts'] == null ? '' : ' · ${_value(item['counts'])}'}',
            ),
          ),
        ],
        for (final item in capacity) ...[
          const SizedBox(height: MakoloSpacing.sm),
          MakoloCard(
            child: Text(
              'Capacité ${_text(item['label']) ?? ''} : '
              '${item['unlimited'] == true ? 'sans limite configurée' : '${item['available'] ?? 'à vérifier'} disponible(s)'}',
            ),
          ),
        ],
        for (final item in checkpoints) ...[
          const SizedBox(height: MakoloSpacing.sm),
          MakoloCard(
            child: Text(
              'Contrôle ${_text(item['label']) ?? ''} · ${_text(item['status']) ?? 'à vérifier'}',
            ),
          ),
        ],
      ],
    );
  }

  List<Widget> _liveSections(BuildContext context) {
    final knowledge = _map(payload['knowledge']);
    final coverage = _map(knowledge['coverage']);
    final planned = _map(knowledge['planned_timing']);
    final temporal = _map(knowledge['temporal_observation']);
    final spatial = _map(knowledge['spatial']);
    final facts = _rows(knowledge['facts']);
    final transitions = _map(knowledge['transitions']);
    return [
      MakoloSection(
        title: 'Ce qui est réellement connu',
        child: MakoloCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                switch (_text(coverage['state'])) {
                  'ESTABLISHED' => 'Couverture établie',
                  'PARTIAL' => 'Couverture partielle',
                  _ => 'Informations indisponibles',
                },
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                coverage['state'] == 'PARTIAL'
                    ? 'Certaines observations sont disponibles. Elles ne couvrent pas forcément toute la situation.'
                    : 'Aucun fait actuellement consultable n’est établi. Cela ne signifie pas que rien ne se passe.',
              ),
              const SizedBox(height: MakoloSpacing.sm),
              const Text('L’heure de lecture ne prouve pas l’heure d’un événement.'),
            ],
          ),
        ),
      ),
      const SizedBox(height: MakoloSpacing.lg),
      MakoloSection(
        title: 'Temps et lieux',
        child: MakoloCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Début prévu : ${_text(planned['start_at']) ?? 'à préciser'}'),
              Text('Fin prévue : ${_text(planned['end_at']) ?? 'à préciser'}'),
              Text(
                'Début réellement observé : ${_truth(_text(temporal['truth']))}',
              ),
              for (final entry in spatial.entries) ...[
                const SizedBox(height: MakoloSpacing.sm),
                Text(entry.key == 'participant'
                    ? 'Mon orientation' : 'Orientation opérationnelle'),
                Text(
                  'Destination prévue : ${_text(_map(_map(entry.value)['destination'])['name']) ?? 'non renseignée'}',
                ),
                const Text('Position actuelle : inconnue si non observée.'),
              ],
            ],
          ),
        ),
      ),
      const SizedBox(height: MakoloSpacing.lg),
      MakoloSection(
        title: 'Faits accessibles',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: facts.isEmpty
              ? [
                  const MakoloCard(
                    child: Text(
                      'Aucune observation consultable pour le moment. La couverture peut être partielle ou indisponible.',
                    ),
                  ),
                ]
              : [
                  for (final fact in facts) ...[
                    MakoloCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            switch (_text(fact['domain'])) {
                              'participant' => 'Ma situation',
                              'organizer' => 'Opérations',
                              'institutional' => 'Démarche de mon Espace',
                              _ => 'Fait autorisé',
                            },
                            style: Theme.of(context).textTheme.labelMedium,
                          ),
                          const SizedBox(height: MakoloSpacing.xs),
                          Text(
                            _text(fact['label']) ?? 'Observation',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          Text(_value(fact['value'])),
                          const SizedBox(height: MakoloSpacing.sm),
                          Text(
                            '${_truth(_text(fact['truth']))} · Source : ${_text(fact['source']) ?? 'non renseignée'}'
                            '${fact['occurred_at'] == null ? ' · Heure inconnue' : ' · ${fact['occurred_at']}'}',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                  ],
                ],
        ),
      ),
      if (transitions['state'] == 'unavailable') ...[
        const SizedBox(height: MakoloSpacing.lg),
        const MakoloSection(
          title: 'Changements',
          child: MakoloCard(
            child: Text(
              'Aucun historique de changements vérifiable n’est disponible. Aucun fil Live n’est simulé.',
            ),
          ),
        ),
      ],
    ];
  }
}
