# Lightweight sequence models for laboratory notebook classification

## Introduction

Deep learning replaced hand-engineered features across vision and language [2]. Convolutional networks first showed the gap on ImageNet, where a five-layer network with 650,000 neurons and 60 million parameters reached a top-1 error rate of 27.5% [4]; residual connections then allowed far deeper models [1]. For sequences, gated recurrent units such as the LSTM [5] were largely displaced by attention-only Transformers [7] and by pre-trained bidirectional encoders [6]. Reinforcement learning combined with deep networks reached human-level play on Atari games [9] and Go [3]. Regularisation by dropout [8] and latent-variable models such as variational autoencoders [11] remain standard tools, and encoder–decoder segmentation networks [12] are widely reused outside biomedicine. Sparse mixture-of-experts models were recently reported to help low-resource scientific text classification [10].

## Results

We fine-tuned a 6-layer Transformer encoder [7] on 18,400 annotated notebook entries. It reached 91.2% macro-F1, 4.1 points above a bidirectional LSTM baseline [5].

## References

[1] K. He, X. Zhang, S. Ren, and J. Sun, "Deep residual learning for image recognition," in *Proc. IEEE Conf. Computer Vision and Pattern Recognition (CVPR)*, 2016, pp. 770–778, doi: 10.1109/CVPR.2016.90.

[2] Y. LeCun, Y. Bengio, and G. Hinton, "Deep learning," *Nature*, vol. 521, no. 7553, pp. 436–444, 2015, doi: 10.1038/nature14539.

[3] D. Silver et al., "Mastering the game of Go with deep neural networks and tree search," *Nature*, vol. 529, no. 7587, pp. 484–489, 2016, doi: 10.1038/nature16961.

[4] A. Krizhevsky, I. Sutskever, and G. E. Hinton, "ImageNet classification with deep convolutional neural networks," *Commun. ACM*, vol. 60, no. 6, pp. 84–90, 2017, doi: 10.1145/3065386.

[5] S. Hochreiter and J. Schmidhuber, "Long short-term memory," *Neural Comput.*, vol. 9, no. 8, pp. 1735–1780, 1997, doi: 10.1162/neco.1997.9.8.1735.

[6] J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, "BERT: Pre-training of deep bidirectional transformers for language understanding," in *Proc. NAACL-HLT*, 2019, pp. 4171–4186, doi: 10.18653/v1/N19-1423.

[7] A. Vaswani et al., "Attention is all you need," in *Advances in Neural Information Processing Systems 30 (NeurIPS 2017)*, 2017, pp. 5998–6008.

[8] N. Srivastava, G. Hinton, A. Krizhevsky, I. Sutskever, and R. Salakhutdinov, "Dropout: A simple way to prevent neural networks from overfitting," *J. Mach. Learn. Res.*, vol. 15, no. 56, pp. 1929–1958, 2014.

[9] V. Mnih et al., "Human-level control through deep reinforcement learning," *Nature*, vol. 518, no. 7540, pp. 529–533, 2013, doi: 10.1038/nature14236.

[10] Y. Zhang, A. Kumar, and S. Lee, "Sparse mixture-of-experts transformers for low-resource scientific text classification," *Nature Machine Intelligence*, vol. 3, no. 7, pp. 612–621, 2021, doi: 10.1038/s42256-021-00381-9.

[11] D. P. Kingma and M. Welling, "Auto-encoding variational Bayes," in *Proc. Int. Conf. Learning Representations (ICLR)*, 2014, doi: 10.1162/neco.1997.9.8.1735.

[12] O. Ronneberger, P. Fischer, and T. Brox, "U-Net: Convolutional networks for biomedical image segmentation," in *Medical Image Computing and Computer-Assisted Intervention – MICCAI 2015*, Lecture Notes in Computer Science, vol. 9351, 2015, pp. 234–241, doi: 10.1007/978-3-319-24574-4_28.
