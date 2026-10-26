import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/projection_contract.dart';

/// Owner-backed native reading surface. Sharing requires a separately
/// authorized owner capability; it is not inferred from Passport availability.
class MePassportScreen extends StatefulWidget {
  const MePassportScreen({super.key, required this.api});
  final MakoloApiClient api;

  @override
  State<MePassportScreen> createState() => _MePassportScreenState();
}

class _MePassportScreenState extends State<MePassportScreen> {
  late Future<Map<String, dynamic>> _future;
  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Map<String, dynamic>> _load() async {
    final response = await widget.api.get('api/v1/me/passport/');
    return ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'personal.me.passport',
    ).data;
  }

  void _retry() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Passeport Makolo')),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          if (snapshot.hasError) {
            return Center(
              child: TextButton.icon(
                onPressed: _retry,
                icon: const Icon(Icons.refresh),
                label: const Text('Réessayer'),
              ),
            );
          }
          return const Center(child: CircularProgressIndicator.adaptive());
        }
        return _PassportBody(data: snapshot.data!);
      },
    ),
  );
}

class _PassportBody extends StatelessWidget {
  const _PassportBody({required this.data});
  final Map<String, dynamic> data;

  static Map<String, dynamic> _map(Object? value) => value is Map
      ? value.map((key, item) => MapEntry(key.toString(), item))
      : <String, dynamic>{};
  static String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
  static List<Map<String, dynamic>> _rows(Object? value) =>
      value is List ? value.whereType<Map>().map(_map).toList() : const [];

  @override
  Widget build(BuildContext context) {
    final identity = _map(data['identity']);
    final declared = _map(data['declared']);
    final established = _map(data['established']);
    final issued = _map(data['issued']);
    final name =
        _text(identity['display_name']) ??
        _text(identity['name']) ??
        _text(identity['username']) ??
        'Mon passeport';
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 40),
      children: [
        Container(
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [MakoloColors.indigo, MakoloColors.deep],
            ),
            borderRadius: BorderRadius.circular(MakoloRadii.large),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.badge_outlined, color: Colors.white, size: 40),
              const SizedBox(height: MakoloSpacing.md),
              Text(
                name,
                style: Theme.of(context).textTheme.headlineSmall
                    ?.copyWith(color: Colors.white),
              ),
            ],
          ),
        ),
        _section(
          context,
          'Intérêts',
          _rows(declared['interests']),
          (row) => _text(_map(row['topic'])['label']),
        ),
        _section(
          context,
          'Ouvert à',
          _rows(declared['open_to']),
          (row) => _text(row['label']),
        ),
        _section(
          context,
          'Faits établis',
          _rows(established['proofs']),
          (row) => _text(row['proof_type_label']),
        ),
        _section(
          context,
          'Attestations',
          _rows(issued['credentials']),
          (row) => _text(row['title']),
        ),
        _section(
          context,
          'Activités',
          _rows(data['activities']),
          (row) => _text(row['title']),
        ),
      ],
    );
  }

  Widget _section(
    BuildContext context,
    String title,
    List<Map<String, dynamic>> rows,
    String? Function(Map<String, dynamic>) readLabel,
  ) {
    final labels = rows.map(readLabel).whereType<String>().toList();
    if (labels.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: MakoloSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: MakoloSpacing.sm),
          for (final label in labels)
            ListTile(contentPadding: EdgeInsets.zero, title: Text(label)),
        ],
      ),
    );
  }
}
