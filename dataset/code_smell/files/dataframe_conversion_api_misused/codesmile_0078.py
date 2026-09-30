# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/5/files/EvalID_91/borzoi_satg_gene_gpu_focused_ism.py#L205-L622
# smelly line(s) in the original file: 351, 412, 571
# smelly line(s) in this file: 153, 214, 373
# ids: codesmile_0078, codesmile_0079, codesmile_0080
def main():
  usage = 'usage: %prog [options] <params> <model> <gene_gtf>'
  parser = OptionParser(usage)
  parser.add_option('--fa', dest='genome_fasta',
      default='%s/data/hg38.fa' % os.environ['BASENJIDIR'],
      help='Genome FASTA for sequences [Default: %default]')
  parser.add_option('-o', dest='out_dir',
      default='satg_out', help='Output directory [Default: %default]')
  parser.add_option('--rc', dest='rc',
      default=0, type='int',
      help='Ensemble forward and reverse complement predictions [Default: %default]')
  parser.add_option('-f', dest='folds',
      default='0', type='str',
      help='Model folds to use in ensemble [Default: %default]')
  parser.add_option('--shifts', dest='shifts',
      default='0', type='str',
      help='Ensemble prediction shifts [Default: %default]')
  parser.add_option('--span', dest='span',
      default=0, type='int',
      help='Aggregate entire gene span [Default: %default]')
  parser.add_option('--clip_soft', dest='clip_soft',
      default=None, type='float',
      help='Model clip_soft setting [Default: %default]')
  parser.add_option('--no_transform', dest='no_transform',
      default=0, type='int',
      help='Run gradients with no inverse transforms [Default: %default]')
  parser.add_option('--pseudo_qtl', dest='pseudo_qtl',
      default=None, type='float',
      help='Quantile of predicted scalars to choose as pseudo count [Default: %default]')
  parser.add_option('--aggregate_tracks', dest='aggregate_tracks',
      default=None, type='int',
      help='Run gradients with no inverse transforms [Default: %default]')
  parser.add_option('-t', dest='targets_file',
      default=None, type='str',
      help='File specifying target indexes and labels in table format')
  parser.add_option('--tissue_files', dest='tissue_files',
      default=None, type='str',
      help='Comma-separated list of files containing saliency scores (h5 format).')
  parser.add_option('--tissues', dest='tissues',
      default=None, type='str',
      help='Comma-separated list of tissue names.')
  parser.add_option('--tissue', dest='tissue',
      default=None, type='str',
      help='Tissue name to filter on in gene_file.')
  parser.add_option('--main_tissue_ix', dest='main_tissue_ix',
      default=0, type='int',
      help='Main tissue index.')
  parser.add_option('--ism_size', dest='ism_size',
      default=192, type='int',
      help='Length of sequence window to run ISM across.')
  parser.add_option('--gene_file', dest='gene_file',
      default=None, type='str',
      help='Csv-file of gene metadata.')
  parser.add_option('--max_n_genes', dest='max_n_genes',
      default=10, type='int',
      help='Maximum number of genes in the GTF to compute ISMs for [Default: %default]')
  parser.add_option('--gaussian_sigma', dest='gaussian_sigma',
      default=8, type='int',
      help='Sigma value for 1D gaussian smoothing filter [Default: %default]')
  parser.add_option('--min_padding', dest='min_padding',
      default=65536, type='int',
      help='Minimum crop to apply to scores before searching for smoothed maximum [Default: %default]')

  (options, args) = parser.parse_args()

  if len(args) == 3:
    # single worker
    params_file = args[0]
    model_folder = args[1]
    genes_gtf_file = args[2]
  else:
    parser.error('Must provide parameter file, model folder and GTF file')

  if not os.path.isdir(options.out_dir):
    os.mkdir(options.out_dir)

  options.folds = [int(fold) for fold in options.folds.split(',')]
  options.shifts = [int(shift) for shift in options.shifts.split(',')]

  options.tissue_files = [tissue for tissue in options.tissue_files.split(",")]
  options.tissues = [tissue for tissue in options.tissues.split(",")]

  #################################################################
  # read parameters and targets

  # read model parameters
  with open(params_file) as params_open:
    params = json.load(params_open)
  params_model = params['model']
  params_train = params['train']
  seq_len = params_model['seq_length']

  if options.targets_file is None:
    parser.error('Must provide targets table to properly handle strands.')
  else:
    targets_df = pd.read_csv(options.targets_file, sep='\t', index_col=0)

  # prep strand
  orig_new_index = dict(zip(targets_df.index, np.arange(targets_df.shape[0])))
  targets_strand_pair = np.array([orig_new_index[ti] for ti in targets_df.strand_pair])
  targets_strand_df = targets_prep_strand(targets_df)
  num_targets = len(targets_strand_df)

  # specify relative target indices
  targets_df['row_index'] = np.arange(len(targets_df), dtype='int32')

  #################################################################
  # load first model fold to get parameters

  seqnn_model = seqnn.SeqNN(params_model)
  seqnn_model.restore(model_folder + "/f0c0/model0_best.h5", 0, by_name=False)
  seqnn_model.build_slice(targets_df.index, False)
  # seqnn_model.build_ensemble(options.rc, options.shifts)

  model_stride = seqnn_model.model_strides[0]
  model_crop = seqnn_model.target_crops[0]
  target_length = seqnn_model.target_lengths[0]

  #################################################################
  # read genes

  # parse GTF
  transcriptome = bgene.Transcriptome(genes_gtf_file)

  # order valid genes
  genome_open = pysam.Fastafile(options.genome_fasta)
  gene_list = sorted(transcriptome.genes.keys())
  num_genes = len(gene_list)

  #Make copy of unfiltered gene list
  gene_list_all = gene_list.copy()

  #################################################################
  # load tissue gene list

  #Load gene dataframe and select tissue
  gene_df = pd.read_csv(options.gene_file, sep='\t')
  gene_df = gene_df.query("tissue == '" + str(options.tissue) + "'").copy().reset_index(drop=True)
  gene_df = gene_df.drop(columns=['Unnamed: 0'])

  print("len(gene_df) = " + str(len(gene_df)))

  #Truncate by maximum number of genes
  gene_df = gene_df.iloc[:options.max_n_genes].copy().reset_index(drop=True)

  #Get list of genes for tissue
  tissue_genes = gene_df['gene_base'].values.tolist()

  #print("len(tissue_genes) = " + str(len(tissue_genes)))

  #Filter transcriptome gene list
  gene_list = [gene for gene in gene_list if gene.split(".")[0] in set(tissue_genes)]
  num_genes = len(gene_list)

  print("num_genes = " + str(num_genes))

  #################################################################
  # load h5 scores

  seqs = None
  strands = None
  chrs = None
  starts = None
  ends = None
  genes = None
  all_scores = []
  pseudo_counts = []

  for scores_h5_file, scores_h5_tissue in zip(options.tissue_files, options.tissues) :

    print("Reading '" + scores_h5_file + "'")

    with h5py.File(scores_h5_file, 'r') as score_file:

      #Get scores and onehots
      scores = score_file['grads'][()][..., 0]
      seqs = score_file['seqs'][()]

      #Get auxiliary information
      strands = score_file['strand'][()]
      strands = np.array([strands[j].decode() for j in range(strands.shape[0])])

      chrs = score_file['chr'][()]
      chrs = np.array([chrs[j].decode() for j in range(chrs.shape[0])])

      starts = np.array(score_file['start'][()])
      ends = np.array(score_file['end'][()])

      genes = score_file['gene'][()]
      genes = np.array([genes[j].decode() for j in range(genes.shape[0])]) #.split(".")[0]

      gene_dict = {gene : gene_i for gene_i, gene in enumerate(genes.tolist())}

      #Get index of rows to keep
      keep_index = []
      for gene in gene_list :
        keep_index.append(gene_dict[gene])

      #Optionally compute pseudo-counts
      if options.aggregate_tracks is not None and options.pseudo_qtl is not None :

        #Load gene dataframe and select active tissue
        gene_df_all = pd.read_csv(options.gene_file, sep='\t')
        gene_df_all = gene_df_all.query("tissue == '" + str(scores_h5_tissue) + "'").copy().reset_index(drop=True)
        gene_df_all = gene_df_all.drop(columns=['Unnamed: 0'])

        #Get list of genes for active tissue
        tissue_genes_all = gene_df_all['gene_base'].values.tolist()

        #Filter transcriptome gene list
        gene_list_tissue = [gene for gene in gene_list_all if gene.split(".")[0] in set(tissue_genes_all)]
        num_genes_tissue = len(gene_list_tissue)

        print(" - num_genes_tissue = " + str(num_genes_tissue))

        #Get index of genes beloning to active tissue
        gene_index = []
        for gene in gene_list_tissue :
          gene_index.append(gene_dict[gene])

        #Compute pseudo-count
        pseudo_count = np.quantile(np.array(score_file['preds'][()][gene_index, 0]), q=options.pseudo_qtl)
        pseudo_counts.append(pseudo_count)

      #Filter/sub-select data
      scores = scores[keep_index, ...]
      seqs = seqs[keep_index, ...]
      strands = strands[keep_index]
      chrs = chrs[keep_index]
      starts = starts[keep_index]
      ends = ends[keep_index]
      genes = genes[keep_index]

      #Append input-gated scores
      all_scores.append((scores * seqs)[None, ...])

      #Collect garbage
      gc.collect()

  #Collect final scores
  scores = np.concatenate(all_scores, axis=0)

  print("scores.shape = " + str(scores.shape))

  #Collect pseudo-counts
  pseudo_count = 0.
  if options.aggregate_tracks is not None and options.pseudo_qtl is not None :
    pseudo_count = np.array(pseudo_counts, dtype='float32')[None, :]

    print("pseudo_count = " + str(np.round(pseudo_count, 2)))
  else :
    print("pseudo_count = " + str(round(pseudo_count, 2)))

  #################################################################
  # setup output

  # choose gene sequences
  genes_chr = chrs.tolist()
  genes_start = starts.tolist()
  genes_end = ends.tolist()
  genes_strand = strands.tolist()

  #################################################################
  # calculate ism start and end positions per gene

  print("main_tissue_ix = " + str(options.main_tissue_ix))

  genes_ism_start = []
  genes_ism_end = []
  for gi in range(len(gene_list)) :
    score_2 = scores[options.main_tissue_ix, gi, ...]
    score_1 = np.mean(scores[np.arange(scores.shape[0]) != options.main_tissue_ix, gi, ...], axis=0)

    diff_score = np.sum(score_2 - score_1, axis=-1)

    #Apply gaussian filter
    diff_score = gaussian_filter1d(diff_score.astype('float32'), sigma=options.gaussian_sigma, truncate=2).astype('float16')

    max_pos = np.argmax(diff_score[options.min_padding:-options.min_padding]) + options.min_padding

    genes_ism_start.append(max_pos - options.ism_size // 2)
    genes_ism_end.append(max_pos + options.ism_size // 2)

  #################################################################
  # predict ISM scores, write output

  print("clip_soft = " + str(options.clip_soft))

  print("n genes = " + str(len(genes_chr)))

  # loop over folds
  for fold_ix in options.folds :
    print("-- Fold = " + str(fold_ix) + " --")

    # (re-)initialize HDF5
    scores_h5_file = '%s/ism_f%dc0.h5' % (options.out_dir, fold_ix)
    if os.path.isfile(scores_h5_file):
      os.remove(scores_h5_file)
    scores_h5 = h5py.File(scores_h5_file, 'w')
    scores_h5.create_dataset('seqs', dtype='bool',
      shape=(num_genes, options.ism_size, 4))
    scores_h5.create_dataset('isms', dtype='float16',
      shape=(num_genes, options.ism_size, 4, num_targets // (options.aggregate_tracks if options.aggregate_tracks is not None else 1)))
    scores_h5.create_dataset('gene', data=np.array(gene_list, dtype='S'))
    scores_h5.create_dataset('chr', data=np.array(genes_chr, dtype='S'))
    scores_h5.create_dataset('start', data=np.array(genes_start))
    scores_h5.create_dataset('end', data=np.array(genes_end))
    scores_h5.create_dataset('ism_start', data=np.array(genes_ism_start))
    scores_h5.create_dataset('ism_end', data=np.array(genes_ism_end))
    scores_h5.create_dataset('strand', data=np.array(genes_strand, dtype='S'))

    # load model fold
    seqnn_model = seqnn.SeqNN(params_model)
    seqnn_model.restore(model_folder + "/f" + str(fold_ix) + "c0/model0_best.h5", 0, by_name=False)
    seqnn_model.build_slice(targets_df.index, False)

    track_scale = targets_df.iloc[0]['scale']
    track_transform = 3. / 4.

    for shift in options.shifts :
      print('Processing shift %d' % shift, flush=True)

      for rev_comp in ([False, True] if options.rc == 1 else [False]) :

        if options.rc == 1 :
          print('Fwd/rev = %s' % ('fwd' if not rev_comp else 'rev'), flush=True)

        seq_1hots = []
        gene_slices = []
        gene_targets = []

        for gi, gene_id in enumerate(gene_list):

          if gi % 50 == 0 :
            print('Processing %d, %s' % (gi, gene_id), flush=True)

          gene = transcriptome.genes[gene_id]

          # make sequence
          seq_1hot = make_seq_1hot(genome_open, genes_chr[gi], genes_start[gi], genes_end[gi], seq_len)
          seq_1hot = dna_io.hot1_augment(seq_1hot, shift=shift)

          # determine output sequence start
          seq_out_start = genes_start[gi] + model_stride*model_crop
          seq_out_len = model_stride*target_length

          # determine output positions
          gene_slice = gene.output_slice(seq_out_start, seq_out_len, model_stride, options.span == 1)

          # determine ism window
          gene_ism_start = genes_ism_start[gi]
          gene_ism_end = genes_ism_end[gi]

          if rev_comp:
            seq_1hot = dna_io.hot1_rc(seq_1hot)
            gene_slice = target_length - gene_slice - 1

            gene_ism_start = seq_len - genes_ism_end[gi] - 1
            gene_ism_end = seq_len - genes_ism_start[gi] - 1

          # slice relevant strand targets
          if genes_strand[gi] == '+':
            gene_strand_mask = (targets_df.strand != '-') if not rev_comp else (targets_df.strand != '+')
          else:
            gene_strand_mask = (targets_df.strand != '+') if not rev_comp else (targets_df.strand != '-')

          gene_target = np.array(targets_df.index[gene_strand_mask].values)

          # broadcast to singleton batch
          seq_1hot = seq_1hot[None, ...]
          gene_slice = gene_slice[None, ...]
          gene_target = gene_target[None, ...]

          # ism computation
          ism = get_ism(
              seqnn_model,
              seq_1hot,
              gene_ism_start,
              gene_ism_end,
              head_i=0,
              target_slice=gene_target,
              pos_slice=gene_slice,
              track_scale=track_scale,
              track_transform=track_transform,
              clip_soft=options.clip_soft,
              pseudo_count=pseudo_count,
              no_transform=options.no_transform == 1,
              aggregate_tracks=options.aggregate_tracks,
              use_mean=False,
              use_ratio=False,
              use_logodds=False,
          )

          # undo augmentations and save ism
          ism = unaugment_grads(ism, fwdrc=(not rev_comp), shift=shift)

          # write to HDF5
          scores_h5['isms'][gi] += ism[genes_ism_start[gi]:genes_ism_end[gi], ...]

          # collect garbage
          gc.collect()

    # save sequences and normalize isms by total size of ensemble
    for gi, gene_id in enumerate(gene_list):

      # re-make original sequence
      seq_1hot = make_seq_1hot(genome_open, genes_chr[gi], genes_start[gi], genes_end[gi], seq_len)

      # write to HDF5
      scores_h5['seqs'][gi] = seq_1hot[genes_ism_start[gi]:genes_ism_end[gi], ...]
      scores_h5['isms'][gi] /= float((len(options.shifts) * (2 if options.rc == 1 else 1)))

    # collect garbage
    gc.collect()

  # close files
  genome_open.close()
  scores_h5.close()
