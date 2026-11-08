import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../sync/projection_contract.dart';

/// Reader-only surface for an issued Passport, not an editor or a local copy.
/// Verification tokens prove issuance; only active Sharing grants convey a
/// separate right to read a non-public issued document.
class PassportDocumentReaderScreen extends StatefulWidget {
  const PassportDocumentReaderScreen({
    super.key,
    required this.runtime,
    required this.token,
    required this.explicitShare,
  });

  final AppRuntime runtime;
  final String token;
  final bool explicitShare;

  @override
  State<PassportDocumentReaderScreen> createState() =>
      _PassportDocumentReaderScreenState();
}

class _PassportDocumentReaderScreenState
    extends State<PassportDocumentReaderScreen> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _document;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant PassportDocumentReaderScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.token != widget.token ||
        oldWidget.explicitShare != widget.explicitShare ||
        oldWidget.runtime != widget.runtime) {
      unawaited(_load());
    }
  }

  @override
  void dispose() {
    _generation++;
    super.dispose();
  }

  Future<void> _load() async {
    final requestGeneration = ++_generation;
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
        _document = null; // Never reuse another bearer token's content.
      });
    }
    try {
      final api = widget.runtime.api;
      if (api == null || widget.token.isEmpty) {
        throw const FormatException('Document reference unavailable');
      }
      final kind = widget.explicitShare ? 'shared' : 'verify';
      final path =
          'api/v1/sharing/passport/$kind/${Uri.encodeComponent(widget.token)}/';
      final response = !widget.explicitShare && widget.runtime.isAuthenticated
          ? await api.get(path)
          : await api.publicGet(path);
      final envelope = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'sharing.passport.document',
        expectedScope: 'reader',
      );
      final data = envelope.data;
      if (data['document_id'] is! String ||
          data['can_view_content'] is! bool ||
          data['explicit_share'] != widget.explicitShare ||
          (data['can_view_content'] == true && data['payload'] is! Map) ||
          (data['can_view_content'] == false && data['payload'] != null)) {
        throw const FormatException('Invalid Passport reader contract');
      }
      if (!mounted || requestGeneration != _generation) return;
      setState(() {
        _document = data;
        _loading = false;
      });
    } on Object {
      if (!mounted || requestGeneration != _generation) return;
      setState(() {
        _error = widget.explicitShare
            ? 'Ce partage est expiré, révoqué ou indisponible.'
            : 'Ce document ne peut pas être vérifié actuellement.';
        _loading = false;
      });
    }
  }

  static Map<String, dynamic> _map(Object? raw) => raw is Map
      ? raw.map((key, value) => MapEntry(key.toString(), value))
      : <String, dynamic>{};

  static List<Map<String, dynamic>> _rows(Object? raw) =>
      raw is List ? raw.whereType<Map>().map(_map).toList() : const [];

  static String? _text(Object? raw) {
    if (raw == null) return null;
    final value = raw.toString().trim();
    return value.isEmpty ? null : value;
  }

  static String _date(Object? value) {
    final text = _text(value);
    if (text == null) return '';
    final parsed = DateTime.tryParse(text);
    if (parsed == null) return text;
    final local = parsed.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(local.day)}/${two(local.month)}/${local.year} '
        '${two(local.hour)}:${two(local.minute)}';
  }

  Widget _section(String title, List<String> facts, {String? explanation}) {
    final items = facts.where((value) => value.trim().isNotEmpty).toList();
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          if (explanation != null)
            Padding(
              padding: const EdgeInsets.only(top: 3, bottom: 5),
              child: Text(
                explanation,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          for (final fact in items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Text(fact),
            ),
        ],
      ),
    );
  }

  List<Widget> _issuedContent(Map<String, dynamic> payload) {
    final identity = _map(payload['identity']);
    final name = _text(identity['name']);
    final bio = _text(identity['bio']);
    final details = _map(identity['owner_details']);
    return [
      if (name != null)
        Text(name, style: Theme.of(context).textTheme.headlineSmall),
      for (final key in [
        'profession',
        'company_name',
        'organization_name',
        'location',
      ])
        if (_text(identity[key]) != null)
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Text(identity[key].toString()),
          ),
      if (bio != null) ...[
        const SizedBox(height: 14),
        Text(bio, style: Theme.of(context).textTheme.bodyLarge),
      ],
      _section('Liens déclarés', [
        for (final value
            in identity['links'] is List ? identity['links'] as List : const [])
          if (value is List && value.length == 2) '${value[0]} : ${value[1]}',
      ]),
      _section(
        'Informations du titulaire',
        [
          for (final entry in details.entries)
            if (_text(entry.value) != null) '${entry.key} : ${entry.value}',
        ],
        explanation: 'Présentes uniquement dans la version complète autorisée.',
      ),
      _section('Centres d’intérêt', [
        for (final value
            in payload['interests'] is List
                ? payload['interests'] as List
                : const [])
          if (_text(value) != null) value.toString(),
      ], explanation: 'Déclarations du titulaire.'),
      _section('Ouvert à', [
        for (final row in _rows(payload['open_to']))
          [
            row['kind'],
            row['topic'],
          ].map(_text).whereType<String>().join(' · '),
      ], explanation: 'Déclarations du titulaire.'),
      _section('Activités présentées', [
        for (final row in _rows(payload['activities']))
          [
            row['title'],
            row['status'],
          ].map(_text).whereType<String>().join(' · '),
      ]),
      _section(
        'Faits établis',
        [
          for (final row in _rows(payload['proofs']))
            [
              row['label'],
              row['activity'],
            ].map(_text).whereType<String>().join(' · '),
        ],
        explanation: 'État enregistré à l’émission ; vérifier la source pour l’état actuel.',
      ),
      _section(
        'Attestations délivrées',
        [
          for (final row in _rows(payload['credentials']))
            [
              row['title'],
              row['issuer'],
              row['status'],
            ].map(_text).whereType<String>().join(' · '),
        ],
        explanation:
            'Une attestation peut avoir été révoquée depuis cette émission.',
      ),
      _section('Vérifications', [
        for (final row in _rows(payload['trust_verifications']))
          [
            row['label'],
            row['valid_until'],
          ].map(_text).whereType<String>().join(' · '),
      ]),
      _section('Équipes et Espaces', [
        for (final row in _rows(payload['team_affiliations']))
          [
            row['team'],
            row['space'],
          ].map(_text).whereType<String>().join(' · '),
      ]),
      _section('Groupes', [
        for (final row in _rows(payload['group_affiliations']))
          _text(row['name']) ?? '',
      ]),
      _section('Espaces accessibles', [
        for (final row in _rows(payload['authorized_space_affiliations']))
          _text(row['name']) ?? '',
      ]),
      _section('Mandats', [
        for (final row in _rows(payload['active_space_mandates']))
          [
            row['role'],
            row['space'],
          ].map(_text).whereType<String>().join(' · '),
      ]),
      _section('Équipes du Space', [
        for (final row in _rows(payload['space_teams']))
          _text(row['name']) ?? '',
      ]),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final doc = _document;
    final canRead = doc?['can_view_content'] == true;
    final payload = canRead ? _map(doc?['payload']) : <String, dynamic>{};
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.explicitShare ? 'Passeport partagé' : 'Vérifier un Passeport',
        ),
        actions: [
          IconButton(
            tooltip: 'Actualiser les droits du document',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_outlined),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.link_off_rounded, size: 40),
                    const SizedBox(height: 16),
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: _load,
                      child: const Text('Réessayer'),
                    ),
                  ],
                ),
              ),
            )
          : ListView(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 48),
              children: [
                Text(
                  doc?['document_id']?.toString() ?? '',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 6),
                Text('Émis le ${_date(doc?['issued_at'])}'),
                Text(
                  'Variante : ${doc?['variant'] ?? ''} · '
                  'Identifiant : ${doc?['public_identifier'] ?? ''}',
                ),
                if (widget.explicitShare)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      'Partage volontaire · expiration : '
                      '${_date(doc?['expires_at'])}',
                    ),
                  ),
                const SizedBox(height: 16),
                if (doc?['revoked'] == true)
                  const Text('Cette version a été révoquée.')
                else if (doc?['integrity_ok'] != true)
                  const Text(
                    'L’intégrité de cette version ne peut pas être confirmée.',
                  )
                else
                  const Text(
                    'L’émission est enregistrée par Makolo. '
                    'Ce document ne constitue pas une certification globale '
                    'des déclarations présentées.',
                  ),
                if (!canRead)
                  const Padding(
                    padding: EdgeInsets.only(top: 20),
                    child: Text(
                      'Le contenu n’est pas disponible pour ce lecteur. '
                      'Un lien de vérification ne donne pas accès aux données privées.',
                    ),
                  )
                else ...[
                  const Divider(height: 42),
                  ..._issuedContent(payload),
                  const SizedBox(height: 20),
                  Text(
                    'Version datée : les faits et droits vivants restent '
                    'sous l’autorité de leurs domaines propriétaires.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ],
            ),
    );
  }
}
