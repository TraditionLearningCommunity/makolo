import 'package:flutter/material.dart';

import '../app/providers.dart';
import '../app/runtime/actor_context.dart';
import 'active_context_avatar.dart';
import '../data/local/profile_store.dart';
import '../design/behavior_primitives.dart';
import '../design/makolo_theme.dart';
import 'actor_selector.dart';

Future<void> showMakoloAvatarSheet(
  BuildContext context, {
  required AppRuntime runtime,
  VoidCallback? onConnections,
  VoidCallback? onEditProfile,
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
      onEditProfile: onEditProfile,
      onBilling: onBilling,
      onSettings: onSettings,
      onSwitchAccount: onSwitchAccount,
      onLogout: onLogout,
      onSelectActor: () => showMakoloActorPicker(context, runtime: runtime),
    ),
  );
}

class MakoloAvatarSheet extends StatelessWidget {
  const MakoloAvatarSheet({
    super.key,
    required this.runtime,
    this.onConnections,
    this.onEditProfile,
    this.onBilling,
    this.onSettings,
    this.onSwitchAccount,
    this.onLogout,
    this.onSelectActor,
  });

  final AppRuntime runtime;
  final VoidCallback? onConnections;
  final VoidCallback? onEditProfile;
  final VoidCallback? onBilling;
  final VoidCallback? onSettings;
  final VoidCallback? onSwitchAccount;
  final VoidCallback? onLogout;
  final VoidCallback? onSelectActor;

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
          final actor =
              runtime.actorContext?.value ?? const PersonalActorContext();
          final activationValue = identity?['activation'];
          final activation = activationValue is Map ? activationValue : null;
          final completionPercentage = activation?['percentage'];
          final displayName = identity?['display_name'] as String?;
          final connectedAccountName = displayName?.trim().isNotEmpty == true
              ? displayName!
              : 'Profil Makolo';
          final usernameValue = identity?['username'];
          final firstLetter =
              displayName != null && displayName.trim().isNotEmpty
              ? displayName.trim().substring(0, 1).toUpperCase()
              : null;
          final avatarValue = identity?['avatar_url'];
          final baseUri = runtime.api?.baseUri;
          final avatarUri =
              avatarValue is String && avatarValue.isNotEmpty && baseUri != null
              ? baseUri.resolve(avatarValue)
              : null;
          final safeAvatar =
              avatarUri != null &&
              (avatarUri.scheme == 'https' || avatarUri.scheme == 'http') &&
              avatarUri.host == baseUri!.host;

          return Semantics(
            container: true,
            label: actor is SpaceActorContext
                ? 'Espace actif et compte connecté'
                : 'Compte personnel et actions globales',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor: Theme.of(context)
                          .colorScheme
                          .primaryContainer,
                      foregroundColor: Theme.of(context)
                          .colorScheme
                          .onPrimaryContainer,
                      child: ClipOval(
                        child: ActiveContextAvatar(
                          runtime: runtime,
                          actor: actor,
                          size: 48,
                          personalLetter: firstLetter,
                          personalUrl: safeAvatar ? avatarUri.toString() : null,
                          personalRevision: snapshot.data?.receivedAt,
                        ),
                      ),
                    ),
                    const SizedBox(width: MakoloSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (actor is SpaceActorContext) ...[
                            Text(
                              'Espace actif',
                              style: Theme.of(context).textTheme.labelMedium,
                            ),
                            StreamBuilder(
                              stream: runtime.space?.watchInventory(),
                              builder: (context, spaces) => Text(
                                activeSpaceName(actor.space, spaces.data),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                            ),
                          ] else
                            Text(
                              connectedAccountName,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          if (actor is PersonalActorContext &&
                              usernameValue is String &&
                              usernameValue.trim().isNotEmpty)
                            Text(
                              '@$usernameValue',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          if (actor is PersonalActorContext &&
                              completionPercentage is int &&
                              completionPercentage >= 0 &&
                              completionPercentage < 100 &&
                              activation?['is_complete'] != true)
                            Padding(
                              padding: const EdgeInsets.only(
                                top: MakoloSpacing.xs,
                              ),
                              child: Row(
                                children: [
                                  Text(
                                    '$completionPercentage % renseigné',
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall,
                                  ),
                                  if (onEditProfile != null) ...[
                                    const SizedBox(width: MakoloSpacing.xs),
                                    Flexible(
                                      child: TextButton(
                                        key: const Key(
                                          'avatar-complete-profile',
                                        ),
                                        onPressed: () =>
                                            _closeThen(context, onEditProfile!),
                                        style: TextButton.styleFrom(
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: MakoloSpacing.xs,
                                          ),
                                          visualDensity: VisualDensity.compact,
                                          alignment: Alignment.centerLeft,
                                        ),
                                        child: const Text(
                                          'Compléter les informations',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: TextStyle(fontSize: 12),
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
                if (actor is SpaceActorContext) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  Text(
                    'Compte connecté : $connectedAccountName',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
                const SizedBox(height: MakoloSpacing.md),
                MakoloActorSelectorTile(
                  runtime: runtime,
                  onTap: onSelectActor == null
                      ? null
                      : () => _closeThen(context, onSelectActor!),
                ),
                if (onConnections != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.xs,
                    leading: const Icon(Icons.link_outlined),
                    title: const Text('Connexions'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onConnections!),
                  ),
                if (onBilling != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.xs,
                    leading: const Icon(Icons.credit_card_outlined),
                    title: const Text('Abonnement & facturation'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onBilling!),
                  ),
                if (onSettings != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.xs,
                    leading: const Icon(Icons.settings_outlined),
                    title: const Text('Paramètres'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onSettings!),
                  ),
                if (onSwitchAccount != null || onLogout != null)
                  const Divider(height: MakoloSpacing.md),
                if (onSwitchAccount != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.xs,
                    leading: const Icon(Icons.switch_account_outlined),
                    title: const Text('Changer de compte'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _closeThen(context, onSwitchAccount!),
                  ),
                if (onLogout != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    minVerticalPadding: MakoloSpacing.xs,
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
