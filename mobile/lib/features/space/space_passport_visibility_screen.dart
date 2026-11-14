import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../network/api_error.dart';

/// Uses only the visibility settings actually owned by Organizations.
class SpacePassportVisibilityScreen extends StatefulWidget {
  const SpacePassportVisibilityScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });
  final AppRuntime runtime;
  final String slug;

  @override
  State<SpacePassportVisibilityScreen> createState() =>
      _SpacePassportVisibilityScreenState();
}

class _SpacePassportVisibilityScreenState
    extends State<SpacePassportVisibilityScreen> {
  bool loading = true, saving = false, authorized = false;
  bool publicProfile = false, searchable = false;
  String? error, expectedId;
  int revision = 0;

  SpaceActorContext? get actor {
    final active = widget.runtime.actorContext?.value;
    return active is SpaceActorContext && active.space.slug == widget.slug
        ? active
        : null;
  }

  String get root =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/';

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(onActorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => unawaited(load()));
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(onActorChanged);
    super.dispose();
  }

  void onActorChanged() {
    ++revision;
    if (!mounted) return;
    setState(() {
      authorized = false;
      expectedId = null;
      error = null;
    });
    if (actor != null) {
      unawaited(load());
    } else {
      setState(() => loading = false);
    }
  }

  Future<void> load() async {
    final current = actor;
    final api = widget.runtime.api;
    final ticket = ++revision;
    if (current == null || api == null) {
      if (mounted) {
        setState(() {
          loading = false;
          authorized = false;
          expectedId = null;
        });
      }
      return;
    }
    final id = current.space.id;
    setState(() {
      loading = true;
      authorized = false;
      error = null;
    });
    try {
      final reply = await api.get('${root}us/');
      final data = reply.jsonObject();
      final identity = data['identity'];
      final caps = data['capabilities'];
      if (identity is! Map ||
          caps is! Map ||
          identity['id']?.toString() != id ||
          caps['update_space'] != true ||
          identity['public_profile'] is! bool ||
          identity['searchable'] is! bool) {
        throw const FormatException('Visibility unavailable');
      }
      if (!mounted || ticket != revision || actor?.space.id != id) return;
      setState(() {
        publicProfile = identity['public_profile'] == true;
        searchable = identity['searchable'] == true;
        authorized = true;
        expectedId = id;
        loading = false;
      });
    } on Object {
      if (!mounted || ticket != revision || actor?.space.id != id) return;
      setState(() {
        authorized = false;
        loading = false;
        expectedId = null;
        error = 'Réglages indisponibles.';
      });
    }
  }

  Future<void> change(String field, bool value) async {
    final current = actor;
    final api = widget.runtime.api;
    if (loading ||
        saving ||
        !authorized ||
        current == null ||
        api == null ||
        current.space.id != expectedId) {
      return;
    }
    final id = current.space.id;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      // The PATCH rechecks SPACE_MANAGE at the server.
      await api.patch(root, body: {field: value});
      if (!mounted || actor?.space.id != id) return;
      setState(() {
        if (field == 'public_profile') {
          publicProfile = value;
        } else {
          searchable = value;
        }
      });
      final repo = widget.runtime.space;
      if (repo != null) {
        try {
          await repo.refreshUs(current.space);
          await repo.refreshWorkspace(current.space);
        } on Object {
          // Keep the server-confirmed value; retry freshness on next visit.
        }
      }
      if (!mounted || actor?.space.id != id) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Enregistré.')));
    } on MakoloApiError catch (failure) {
      if (!mounted || actor?.space.id != id) return;
      setState(() {
        error =
            failure.statusCode == 401 ||
                failure.statusCode == 403 ||
                failure.statusCode == 404
            ? 'Accès indisponible.'
            : 'Modification impossible.';
        if (failure.statusCode == 401 ||
            failure.statusCode == 403 ||
            failure.statusCode == 404) {
          authorized = false;
          expectedId = null;
        }
      });
    } on Object {
      if (mounted && actor?.space.id == id) {
        setState(() => error = 'Modification impossible.');
      }
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Confidentialité du Passeport')),
    body: actor == null
        ? const Center(child: Text('Espace indisponible.'))
        : loading
        ? const Center(child: CircularProgressIndicator.adaptive())
        : !authorized
        ? Center(
            child: MakoloActionButton(
              label: error ?? 'Réessayer',
              appearance: MakoloActionAppearance.quiet,
              onPressed: load,
            ),
          )
        : ListView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 30),
            children: [
              SwitchListTile.adaptive(
                title: const Text('Passeport public'),
                contentPadding: EdgeInsets.zero,
                value: publicProfile,
                onChanged: saving
                    ? null
                    : (value) => change('public_profile', value),
              ),
              const Divider(),
              SwitchListTile.adaptive(
                title: const Text('Visible dans la recherche'),
                contentPadding: EdgeInsets.zero,
                value: searchable,
                onChanged: saving
                    ? null
                    : (value) => change('searchable', value),
              ),
              const SizedBox(height: 24),
              Text(
                'Informations publiques',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              const Text('Nom · Présentation · Localisation · Site web'),
              const SizedBox(height: 20),
              Text(
                'Informations internes',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              const Text('Contacts · Équipes internes'),
              if (error != null) ...[
                const SizedBox(height: 16),
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 24),
              MakoloActionButton(
                label: 'Modifier les informations',
                appearance: MakoloActionAppearance.secondary,
                onPressed: () =>
                    context.push('/space/${widget.slug}/us/settings'),
                icon: Icons.edit_outlined,
              ),
            ],
          ),
  );
}
