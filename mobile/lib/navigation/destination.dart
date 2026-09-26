enum MakoloDestination {
  now('/now', 'Maintenant'),
  discover('/discover', 'Découvrir'),
  ongoing('/ongoing', 'En cours'),
  me('/me', 'Moi');

  const MakoloDestination(this.path, this.label);

  final String path;
  final String label;
}

class StructuredDestination {
  const StructuredDestination({
    required this.kind,
    required this.id,
    this.link,
  });

  final String kind;
  final String id;
  final String? link;
}
