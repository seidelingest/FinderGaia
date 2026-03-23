from pymongo import MongoClient

# Une los catálogos "Gaia DR3 XP Sampled Mean Spectrum" y "F1:P1 -> Gaia DR3 + Gaia QsoC". El campo que los relaciona es "source_id".

# Conéctate al servidor MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']  # Sustituye con el nombre de tu base de datos

# Define el pipeline de agregación
pipeline = [
    {
        "$lookup": {
            "from": "Gaia DR3",
            "let": { "source_id": "$source_id" },
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                { "$eq": ["$source_id", "$$source_id"] },
                                { "$eq": ["$has_xp_sampled", True] }
                            ]
                        }
                    }
                }
            ],
            "as": "resultadoLookup"
        }
    },
    {
        "$unwind": "$resultadoLookup"
    },
    {
        "$project": {
            # Renombra los campos de F1:P1 -> Gaia DR3 + Gaia QsoC
            "GaiaSpec_Source_id": "$source_id",
            "GaiaSpec_Solution_id": "$solution_id",
            "GaiaSpec_ra": "$ra",
            "GaiaSpec_dec": "$dec",
            "GaiaSpec_flux": "$flux",
            "GaiaSpec_flux_error": "$flux_error",
            "GaiaSpec_teff_gspphot": "$teff_gspphot",

            # Renombra los campos de Gaia DR3 QsoCandidates
            "Gaia_classprob_dsc_combmod_quasar": "$resultadoLookup.classprob_dsc_combmod_quasar",
            "Gaia_classprob_dsc_combmod_galaxy": "$resultadoLookup.classprob_dsc_combmod_galaxy",
            "Gaia_classprob_dsc_combmod_star": "$resultadoLookup.classprob_dsc_combmod_star",

            "Gaia_vari_best_class_name": "$resultadoLookup.vari_best_class_name",
            "Gaia_vari_best_class_score": "$resultadoLookup.vari_best_class_score",

            "Gaia_phot_g_mean_mag": "$resultadoLookup.phot_g_mean_mag",
            "Gaia_phot_bp_mean_mag": "$resultadoLookup.phot_bp_mean_mag",
            "Gaia_phot_rp_mean_mag": "$resultadoLookup.phot_rp_mean_mag",
            
            "Gaia_non_single_star": "$resultadoLookup.non_single_star"
        }
    },
    {
        "$out": "F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3"  # La colección final
    }
]

# Ejecuta la agregación
db['Gaia DR3 XP Sampled Mean Spectrum'].aggregate(pipeline)
