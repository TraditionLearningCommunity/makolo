import 'package:flutter/material.dart';

import '../app/providers.dart';
import '../data/local/profile_store.dart';
import '../design/behavior_primitives.dart';
import '../design/makolo_theme.dart';

Future<void> showMakoloAvatarSheet(
  BuildContext context, {
  required AppRuntime runtime,
  VoidCallback? onConnections,
  VoidCallback? onBilling,
  VoidCallback? onSettings,
  VoidCallback? onSwitchAccount,
  VoidCallback? onLogout,
}) async {
  await showMakoloBottomSheet<void>(
    context,
    builder: (_) => MakoloAvatarSheet(
      runtime: runtime,
      onConnections: onConnections,
      onBilling: onBilling,
      onSettings: onSettings,
      onSwitchAccount: onSwitchAccount,
      onLogout: onLogout,
    ),
  );
}

class MakoloAvatarSheet extends StatelessWidget {
  const MakoloAvatarSheet({
    super.key,
    required this.runtime,
    this.onConnections,
    this.onBilling,
    this.onSettings,
    this.onSwitchAccount,
    this.onLogout,
  });

  final AppRuntime runtime;
  final VoidCallback? onConnections;
  final VoidCallback? onBilling;
  final VoidCallback? onSettings;
  final VoidCallback? onSwitchAccount;
  final VoidCallback? onLogout;

  Stream<StoredProjection?> get _identityStream =>
      runtime.personal?.watchMe() ?? Stream<StoredProjection?>.value(null);

  Map<String, dynamic>? _identity(StoredProjection? projection) {
    final raw = projection?.payload['identity'];
    if (raw is Map<String, dynamic>) return raw;
    if (raw is Map) return Map<String, dynamic>.from(raw);
    return null;
  }

  void _closeThen(BuildContext context, VoidCallback action) {
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
          final activationPercent = activationPercentage is num
              ? activationPercentage.round()
              : null;
          final showActivation =
              activationPercent != null && activationPercent < 100;
          final firstLetter =
              displayName != null && displayName.trim().isNotEmpty
              ? displayName.trim().substring(0, 1).toUpperCase()
              : null;

          return Semantics(
            container: true,
            label: 'Identité et actions globales',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor:
                          Theme.of(context).colorScheme.primaryContainer,
                      foregroundColor:
                          Theme.of(context).colorScheme.onPrimaryContainer,
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
                          if (showActivation) ...[
                            const SizedBox(height: MakoloSpacing.xs),
                            Text(
                              'Profil Makolo · $activationPercent % activé',
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
                const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.person_pin_circle_outlined),
                  title: Text('Agir comme'),
                  subtitle: Text('Moi'),
                ),
                if (onConnections != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.link_outlined),
                    title: const Text('Connexions'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onConnections!),
                  ),
                if (onBilling != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.credit_card_outlined),
                    title: const Text('Abonnement et facturation'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onBilling!),
                  ),
                if (onSettings != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.settings_outlined),
                    title: const Text('Paramètres'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onSettings!),
                  ),
                if (onSwitchAccount != null || onLogout != null)
                  const Divider(height: MakoloSpacing.lg),
                if (onSwitchAccount != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.switch_account_outlined),
                    title: const Text('Changer de compte'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onSwitchAccount!),
                  ),
                if (onLogout != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.sm,
                    leading: const Icon(Icons.logout),
                    title: const Text('Se déconnecter'),
                    onTap: () => _closeThen(context, onLogout!),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}
