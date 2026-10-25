import 'package:flutter/material.dart';

import '../../features/discovery/discovery_selector.dart';
import '../../network/makolo_api_client.dart';
import 'discovery_possibility_unit.dart';

/// Public Discovery and personal Discovery share one semantic N1 composition.
class PublicPossibilityCard extends StatelessWidget {
  const PublicPossibilityCard({
    super.key,
    required this.item,
    required this.onTap,
    this.onSave,
    this.shareApi,
    this.onSignIn,
    this.onNativeAction,
    this.baseUri,
    this.compact = false,
  });

  final DiscoveryItemPresentation item;
  final VoidCallback onTap;
  final Future<void> Function()? onSave;
  final MakoloApiClient? shareApi;
  final VoidCallback? onSignIn;
  final ValueChanged<String>? onNativeAction;
  final Uri? baseUri;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return DiscoveryPossibilityUnit(
      item: item,
      onOpen: onTap,
      onSave: onSave,
      shareApi: shareApi,
      onSignIn: onSignIn,
      onNativeAction: onNativeAction,
      allowSavePrompt: onSave != null,
      baseUri: baseUri,
      compact: compact,
    );
  }
}
