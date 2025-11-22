docker build -f Dockerfile -t argocd-deployment-bot .
docker rm argocd-deployment-bot
docker create --name argocd-deployment-bot argocd-deployment-bot
docker commit argocd-deployment-bot umairedu/argocd-deployment-bot:latest
docker push umairedu/argocd-deployment-bot:latest
