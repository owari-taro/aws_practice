# 概要
* cloudformation(cfn)で(ECRに登録されたイメージを使う)lambda/SNSをdeployする
* lambdaはSNSにmessageをpublishする

## warning
docker push後にimageを選択しておかないと最新版が使われない、

![](2024-07-12-19-09-20.png)


## 参考
https://dev.classmethod.jp/articles/deploy-container-image-lambda-function-with-cloudformation/


```
aws cloudformation deploy \
  --stack-name lambda-container-test \
  --template-file ./template.yml \
  --parameter-overrides EcrImageUri=905418223580.dkr.ecr.ap-northeast-1.amazonaws.com/hello_lambda:latest \
  --capabilities CAPABILITY_IAM
```
