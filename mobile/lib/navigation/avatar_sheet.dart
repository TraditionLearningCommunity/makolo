import 'package:flutter/material.dart';

import '../app/providers.dart';
import '../data/local/profile_store.dart';
import '../design/behavior_primitives.dart';
import '../design/makolo_theme.dart';

Future<void> showMakoloAvatarSheet(
  BuildContext context, {
  required AppRuntime runtime,
  VoidCallback? onAccount,
  VoidCallback? onSwitchAccount,
  VoidCallback? onLogout,
}) async {
  await showMakoloBottomSheet<void>(
    context,
    builder: (_) => MakoloAvatarSheet(
      runtime: runtime,
      onAccount: onAccount,
      onSwitchAccount: onSwitchAccount,
      onLogout: onLogout,
    ),
  );
}

class MakoloAvatarSheet extends StatefulWidget {
  const MakoloAvatarSheet({
    super.key,
    required this.runtime,
    this.onAccount,
    this.onSwitchAccount,
    this.onLogout,
  });

  final AppRuntime runtime;
  final VoidCallback? onAccount;
  final VoidCallback? onSwitchAccount;
  final VoidCallback? onLogout;

  @override
  State<MakoloAvatarSheet> createState() => _MakoloAvatarSheetState();
}

class _MakoloAvatarSheetState extends State<MakoloAvatarSheet> {
  late final Future<String?> _email = _loadEmail();

  Future<String?> _loadEmail() async {
    final api = widget.runtime.api;
    if (api == null) return null;
    try {
      final response = await api.get('api/v1/accounts/auth/me/');
      final value = response.jsonObject()['email'];
      return value is String && value.trim().isNotEmpty ? value : null;
    } on Object {
      return null;
    }
  }

  Stream<StoredProjection?> get _identityStream =>
      widget.runtime.personal?.watchMe() ??
      Stream<StoredProjection?>.value(null);

  Map<String, dynamic>? _identity(StoredProjection? projection) {
    final raw = projection?.payload['identity'];
    if (raw is Map<String, dynamic>) return raw;
    if (raw is Map) return Map<String, dynamic>.from(raw);
    return null;
  }

  void _closeThen(VoidCallback action) {
    Navigator.of(context).pop();
    WidgetsBinding.instance.addPostFrameCallback((_) => action());
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        MakoloSpacing.lg,
        MakoloSpacing.sm,
        MakoloSpacing.lg,
        MakoloSpacing.lg + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: StreamBuilder<StoredProjection?>(
        stream: _identityStream,
        builder: (context, snapshot) {
          final identity = _identity(snapshot.data);
          final displayName = identity?['display_name'] as String?;
          final activation = identity?['activation'];
          final activationPercentage = activation is Map
              ? activation['percentage']
              : null;
          final firstLetter =
              displayName != null && displayName.trim().isNotEmpty
              ? displayName.trim().substring(0, 1).toUpperCase()
              : null;

          return Semantics(
            container: true,
            label: 'Compte et identité active',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor: Theme.of(context)
                          .colorScheme
                          .primaryContainer,
                      foregroundColor: Theme.of(context)
                          .colorScheme
                          .onPrimaryContainer,
                      child: firstLetter == null
                          ? const Icon(Icons.person_outline)
                          : Text(
                              firstLetter,
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                    ),
                    const SizedBox(width: MakoloSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            displayName?.trim().isNotEmpty == true
                                ? displayName!
                                : 'Profil Makolo',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: MakoloSpacing.xs),
                          FutureBuilder<String?>(
                            future: _email,
                            builder: (context, emailSnapshot) {
                              final email = emailSnapshot.data;
                              if (email == null) {
                                return const SizedBox.shrink();
                              }
                              return Text(
                                email,
                                style: Theme.of(context).textTheme.bodyMedium,
                              );
                            },
                          ),
                          if (activationPercentage is num) ...[
                            const SizedBox(height: MakoloSpacing.sm),
                            Text(
                              'Profil Makolo · ${activationPercentage.round()} % activé',
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.primary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.lg),
                const Divider(height: 1),
                const SizedBox(height: MakoloSpacing.sm),
                const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.person_pin_circle_outlined),
                  title: Text('Contexte actif'),
                  subtitle: Text('Personnel'),
                ),
                if (widget.onAccount != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.manage_accounts_outlined),
                    title: const Text('Compte et paramètres'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(widget.onAccount!),
                  ),
                if (widget.onSwitchAccount != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.switch_account_outlined),
                    title: const Text('Changer de compte'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(widget.onSwitchAccount!),
                  ),
                if (widget.onLogout != null) ...[
                  const Divider(height: MakoloSpacing.lg),
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.logout),
                    title: const Text('Se déconnecter'),
                    onTap: () => _closeThen(widget.onLogout!),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}
