import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import '../../navigation/avatar_sheet.dart';
import '../../navigation/shell_header.dart';
import '../../navigation/space_context_bar.dart';

class MarkScreen extends StatelessWidget {
  const MarkScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  Widget _body(BuildContext context, ActorContext actor) => SafeArea(
    top: false,
    child: Column(
      children: [
        if (actor is SpaceActorContext)
          MakoloSpaceContextBar(runtime: runtime, actor: actor),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(MakoloSpacing.lg),
            children: [
              const Center(child: MakoloMark(size: 64)),
              const SizedBox(height: MakoloSpacing.lg),
              Text(
                'Qu’est-ce que vous avez en tête ?',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: MakoloSpacing.md),
              const Text(
                'Cette entrée sera disponible ici lorsqu’elle pourra vous aider à avancer.',
              ),
            ],
          ),
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final controller = runtime.actorContext;
    return Scaffold(
      appBar: MakoloPrimaryHeader(
        kind: MakoloHeaderKind.mark,
        onAvatar: () => showMakoloAvatarSheet(context, runtime: runtime),
      ),
      body: controller == null
          ? _body(context, const PersonalActorContext())
          : ListenableBuilder(
              listenable: controller,
              builder: (context, _) => _body(context, controller.value),
            ),
    );
  }
}
