# 실험 노트 자동 분류를 위한 경량 신경망 모델

## 서론

딥러닝은 영상과 언어 처리 전반에서 수작업 특징 설계를 대체했다[2]. ImageNet 대회용으로 학습된 합성곱 신경망은 1,200만 장의 고해상도 이미지를 1000개 범주로 분류했고, 테스트 데이터에서 top-5 오류율이 20% 이상이었다[4]. 이후 잔차 연결이 더 깊은 모델 학습을 가능하게 했다[1]. 순차 데이터에서는 LSTM[5]과 사전학습 양방향 인코더[11]가 널리 쓰이며, 최적화에는 Adam[7]이 표준으로 자리 잡았다. 강화학습과 결합한 심층 신경망은 아타리 게임[6]과 바둑[3]에서 인간 수준에 도달했다. 국내에서는 한국어 과학 논문 요약을 위한 경량 트랜스포머[8]가, 분자 특성 예측에는 양자 영감 그래프 신경망[9]이 제안되었다. 측정 장치의 양자적 한계에 대한 고전적 논의[10]는 센서 데이터의 잡음 모델링에도 시사점을 준다.

## 결과

18,400건의 실험 노트로 6층 트랜스포머 인코더를 미세조정한 결과 macro-F1 91.2%를 얻었으며, 이는 LSTM 기준 모델[5]보다 4.1%p 높다.

## 참고문헌

[1] He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image recognition. In *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition* (pp. 770–778). https://doi.org/10.1109/CVPR.2016.90

[2] Hinton, G., LeCun, Y., & Bengio, Y. (2015). Deep learning. *Nature*, 521(7553), 436–444. https://doi.org/10.1038/nature14539

[3] Silver, D., Huang, A., Maddison, C. J., Guez, A., Sifre, L., van den Driessche, G., et al. (2016). Mastering the game of Go with deep neural networks and tree search. *Nature*, 529(7587), 484–489. https://doi.org/10.1038/nature16961

[4] Krizhevsky, A., Sutskever, I., & Hinton, G. E. (2017). ImageNet classification with deep convolutional neural networks. *Communications of the ACM*, 60(6), 84–90. https://doi.org/10.1145/3065386

[5] Hochreiter, S., & Schmidhuber, J. (1997). Long short-term memory. *Neural Computation*, 9(8), 1735–1780. https://doi.org/10.1162/neco.1997.9.8.1735

[6] Mnih, V., Kavukcuoglu, K., Silver, D., Rusu, A. A., Veness, J., Bellemare, M. G., et al. (2015). Human-level control through deep reinforcement learning. *Nature*, 518(7540), 529–533. https://doi.org/10.1038/nature14236

[7] Kingma, D. P., & Ba, J. (2014). Adam: A method for stochastic optimization. arXiv preprint arXiv:1412.6980.

[8] 김지훈, 이서연 (2022). 한국어 과학 논문 요약을 위한 경량 트랜스포머. *정보과학회논문지*, 49(3), 211–220. https://doi.org/10.5626/JOK.2022.49.3.211

[9] Park, S., & Choi, M. (2021). Quantum-inspired graph neural networks for molecular property prediction. *Journal of Chemical Information and Modeling*, 61(8), 3901–3912.

[10] A. Einstein, B. Podolsky, and N. Rosen, Phys. Rev. 48, 777 (1935).

[11] Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. In *Proceedings of NAACL-HLT 2019* (pp. 4171–4186). https://doi.org/10.18653/v1/N19-1423
