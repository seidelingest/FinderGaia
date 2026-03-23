from pymongo import MongoClient

# Une los catálogos "Gaia DR3" y "Gaia DR3 QsoCandidates". El campo que los relaciona es "source_id".
# Solo se tiene en cuenta en "Gaia DR3" los que tengan {"in_qso_candidates": True}

# Conéctate al servidor MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']  # Sustituye con el nombre de tu base de datos

# Define el pipeline de agregación
pipeline = [
    {
        "$match": {"in_qso_candidates": True}
    },
    {
        "$lookup": {
            "from": "Gaia DR3 QsoCandidates",
            "localField": "source_id",
            "foreignField": "source_id",
            "as": "qsoCandidates"
        }
    },
    {
        "$unwind": "$qsoCandidates"
    },
    {
        "$project": {
            # Renombra los campos de Gaia DR3
            "Gaia_Source_id": "$source_id",
            "Gaia_ra_J2016": "$ra",
            "Gaia_dec_J2016": "$dec",
            "Gaia_Gmag": "$phot_g_mean_mag",
            "Gaia_Bmag": "$phot_bp_mean_mag",
            "Gaia_Rmag": "$phot_rp_mean_mag",
            "Gaia_in_qso_candidates": "$in_qso_candidates",
            "Gaia_in_galaxy_candidates": "$in_galaxy_candidates",
            "Gaia_has_xp_continuous": "$has_xp_continuous",
            "Gaia_has_xp_sampled": "$has_xp_sampled",
            "Gaia_classprob_dsc_combmod_quasar": "$classprob_dsc_combmod_quasar",
            "Gaia_classprob_dsc_combmod_galaxy": "$classprob_dsc_combmod_galaxy",
            "Gaia_classprob_dsc_combmod_star": "$classprob_dsc_combmod_star",
            # Renombra los campos de Gaia DR3 QsoCandidates
            "GaiaQsoC_vari_best_class_name": "$qsoCandidates.vari_best_class_name",
            "GaiaQsoC_vari_best_class_score": "$qsoCandidates.vari_best_class_score",
            "GaiaQsoC_intensity_quasar": "$qsoCandidates.intensity_quasar",
            "GaiaQsoC_intensity_quasar_error": "$qsoCandidates.intensity_quasar_error",
            "GaiaQsoC_intensity_hostgalaxy": "$qsoCandidates.intensity_hostgalaxy",
            "GaiaQsoC_intensity_hostgalaxy_error": "$qsoCandidates.intensity_hostgalaxy_error",
            "GaiaQsoC_radius_hostgalaxy": "$qsoCandidates.radius_hostgalaxy",
            "GaiaQsoC_radius_hostgalaxy_error": "$qsoCandidates.radius_hostgalaxy_error",
            "GaiaQsoC_posangle_hostgalaxy": "$qsoCandidates.posangle_hostgalaxy",
            "GaiaQsoC_posangle_hostgalaxy_error": "$qsoCandidates.posangle_hostgalaxy_error",
            "GaiaQsoC_host_galaxy_detected": "$qsoCandidates.host_galaxy_detected",
            "GaiaQsoC_source_selection_flags": "$qsoCandidates.source_selection_flags",
        }
    },
    {
        "$out": "F1:P1 -> Gaia DR3 + Gaia QsoC"  # La colección final
    }
]

# Ejecuta la agregación
db['Gaia DR3'].aggregate(pipeline)
