# smell: NaN Equivalence Comparison Misused (R18)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/5/files/EvalID_77/DEP_xsolution.py#L98-L108
# smelly line(s) in the original file: 103
# smelly line(s) in this file: 12
# ids: codesmile_0148
def extract_each_surface_representations(ids, last_idx, simplex,
                                         surf_ver_sim, vertex):
    for index, row in surf_ver_sim.iterrows():
        v_ = row['vertices']
        e_ = row['edges'] + last_idx
        if v_ is not np.nan and e_ is not np.nan:
            i_ = np.ones(e_.shape[0]) * row['id']
            vertex.append(v_)
            simplex.append(e_)
            ids.append(i_)
            last_idx = e_[-20:].max() + 1
