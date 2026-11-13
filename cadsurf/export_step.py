# Copyright 2026 The CADSurfaceAnalyser authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Écriture du fichier STEP AP214 coloré (un STYLED_ITEM par face).
"""

from .step_parser import Ref


# ============================================================================
# EXPORT STEP COLORÉ
# ============================================================================

def write_colored_step(
    step,
    output_path,
    faces,
    groups,
    group_by_face,
    colors
):

    next_id = (
        max(
            step.ents.keys()
        )
        + 1
    )

    new_lines = []

    def new_entity(text):

        nonlocal next_id

        eid = next_id

        next_id += 1

        new_lines.append(
            "#%d=%s ;"
            % (eid, text)
        )

        return eid

    # ----------------------------------------------------------------------
    # Styles existants
    # ----------------------------------------------------------------------

    face_ids = set(
        faces.keys()
    )

    styles_to_remove = set()

    for sid in step.ids_of(
        "STYLED_ITEM",
        "OVER_RIDING_STYLED_ITEM"
    ):

        a = step.get(
            sid,
            "STYLED_ITEM",
            "OVER_RIDING_STYLED_ITEM"
        )

        if (
            a is not None
            and len(a) >= 3
            and isinstance(a[2], Ref)
            and int(a[2]) in face_ids
        ):

            styles_to_remove.add(
                sid
            )

    # ----------------------------------------------------------------------
    # Création des PRESENTATION_STYLE_ASSIGNMENT
    # ----------------------------------------------------------------------

    styled_items = []

    for group_index, group in enumerate(
        groups,
        start=1
    ):

        rgb = colors[
            group_index
        ]

        r, g, b = rgb

        colour = new_entity(
            "COLOUR_RGB('',%.6f,%.6f,%.6f)"
            % (
                r,
                g,
                b
            )
        )

        fill_colour = new_entity(
            "FILL_AREA_STYLE_COLOUR('',#%d)"
            % colour
        )

        fill_area = new_entity(
            "FILL_AREA_STYLE('',(#%d))"
            % fill_colour
        )

        surface_fill = new_entity(
            "SURFACE_STYLE_FILL_AREA(#%d)"
            % fill_area
        )

        side_style = new_entity(
            "SURFACE_SIDE_STYLE('',(#%d))"
            % surface_fill
        )

        usage = new_entity(
            "SURFACE_STYLE_USAGE(.BOTH.,#%d)"
            % side_style
        )

        assignment = new_entity(
            "PRESENTATION_STYLE_ASSIGNMENT((#%d))"
            % usage
        )

        for fid in sorted(group):

            styled = new_entity(
                "STYLED_ITEM('',(#%d),#%d)"
                % (
                    assignment,
                    fid
                )
            )

            styled_items.append(
                styled
            )

    # ----------------------------------------------------------------------
    # Modifier représentation de présentation existante
    # ----------------------------------------------------------------------

    edits = []

    presentation_ids = step.ids_of(
        "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION"
    )

    if presentation_ids:

        pid = presentation_ids[0]

        a = step.get(
            pid,
            "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION"
        )

        if (
            a is not None
            and len(a) >= 3
        ):

            old_items = a[1]

            items = [
                x
                for x in old_items
                if x not in styles_to_remove
            ]

            items.extend(
                styled_items
            )

            name = (
                str(a[0])
                .replace(
                    "'",
                    "''"
                )
            )

            context = a[2]

            replacement = (
                "#%d="
                "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION"
                "('%s',(%s),#%d) ;"
                % (
                    pid,
                    name,
                    ",".join(
                        "#%d" % x
                        for x in items
                    ),
                    context
                )
            )

            edits.append(
                (
                    step.spans[pid][0],
                    step.spans[pid][1],
                    replacement
                )
            )

    else:

        # ------------------------------------------------------------------
        # Pas de représentation de présentation.
        #
        # On cherche un contexte géométrique.
        # ------------------------------------------------------------------

        context = None

        for rid in step.ids_of(
            "ADVANCED_BREP_SHAPE_REPRESENTATION",
            "MANIFOLD_SURFACE_SHAPE_REPRESENTATION",
            "SHAPE_REPRESENTATION"
        ):

            a = step.get(
                rid,
                "ADVANCED_BREP_SHAPE_REPRESENTATION",
                "MANIFOLD_SURFACE_SHAPE_REPRESENTATION",
                "SHAPE_REPRESENTATION"
            )

            if (
                a is not None
                and len(a) > 0
                and isinstance(
                    a[-1],
                    Ref
                )
            ):

                context = a[-1]

                break

        if context is None:

            raise RuntimeError(
                "Impossible de trouver un contexte "
                "pour la représentation de présentation."
            )

        new_entity(
            "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION"
            "('',(%s),#%d)"
            % (
                ",".join(
                    "#%d" % x
                    for x in styled_items
                ),
                context
            )
        )

    # ----------------------------------------------------------------------
    # Suppression des styles existants
    # ----------------------------------------------------------------------

    for sid in styles_to_remove:

        start, end = step.spans[
            sid
        ]

        text = step.text

        while (
            end < len(text)
            and text[end] in
            " \t\r\n"
        ):
            end += 1

        edits.append(
            (
                start,
                end,
                ""
            )
        )

    # ----------------------------------------------------------------------
    # Insertion des nouvelles entités
    # ----------------------------------------------------------------------

    edits.append(
        (
            step.endsec,
            step.endsec,
            step.nl.join(
                new_lines
            )
            + step.nl
        )
    )

    text = step.text

    for start, end, replacement in sorted(
        edits,
        key=lambda x: x[0],
        reverse=True
    ):

        text = (
            text[:start]
            + replacement
            + text[end:]
        )

    with open(
        output_path,
        "w",
        encoding="latin-1",
        newline=""
    ) as f:

        f.write(text)
