import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../sync/projection_contract.dart';

/// Private Group owner view; only facts returned after membership and
/// authority checks are shown. Mutations remain owned by Groups.
class MeGroupScreen extends StatefulWidget {
  const MeGroupScreen({super.key, required this.api, required this.groupId});
  final MakoloApiClient api;
  final String groupId;

  @override
  State<MeGroupScreen> createState() => _MeGroupScreenState();
}

class _MeGroupScreenState extends State<MeGroupScreen> {
  late Future<Map<String, dynamic>> _detail;

  @override
  void initState() {
    super.initState();
    _detail = _fetch();
  }

  Future<Map<String, dynamic>> _fetch() async {
    final result = await widget.api.get(
      'api/v1/me/collectives/groups/${Uri.encodeComponent(widget.groupId)}/',
    );
    final envelope = ProjectionEnvelope.parse(
      result.jsonObject(),
      expectedProjection: 'personal.group.detail',
    );
    if (envelope.data['id']?.toString() != widget.groupId) {
      throw const FormatException('Invalid Group owner response');
    }
    return envelope.data;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Groupe')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _detail,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            if (snapshot.hasError) {
              return Center(
                child: TextButton.icon(
                  onPressed: () => setState(() => _detail = _fetch()),
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Réessayer'),
                ),
              );
            }
            return const Center(child: CircularProgressIndicator.adaptive());
          }
          final data = snapshot.data!;
          final name = data['name']?.toString() ?? 'Groupe';
          final description = data['description']?.toString();
          final members = data['members'];
          final count = members is Map ? members['active_count'] : null;
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(name, style: Theme.of(context).textTheme.headlineMedium),
              if (description != null && description.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(description, style: Theme.of(context).textTheme.bodyLarge),
              ],
              if (count is int) ...[
                const SizedBox(height: 28),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.groups_outlined),
                  title: Text('$count membres'),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}
