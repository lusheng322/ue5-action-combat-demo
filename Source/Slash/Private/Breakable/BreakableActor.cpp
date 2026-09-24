// Fill out your copyright notice in the Description page of Project Settings.


#include "Breakable/BreakableActor.h"
#include "GeometryCollection/GeometryCollectionComponent.h"
#include "Actors/Treasures/Treasure.h"
#include "Components/CapsuleComponent.h"

ABreakableActor::ABreakableActor()
{
	PrimaryActorTick.bCanEverTick = false;

	GeometryCollection = CreateDefaultSubobject<UGeometryCollectionComponent>(TEXT("GeometryCollection"));
	SetRootComponent(GeometryCollection);
	GeometryCollection->SetGenerateOverlapEvents(true);
	GeometryCollection->SetCollisionResponseToChannel(ECollisionChannel::ECC_Camera, ECollisionResponse::ECR_Ignore);
	GeometryCollection->SetCollisionResponseToChannel(ECollisionChannel::ECC_Pawn, ECollisionResponse::ECR_Ignore);

	Capsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));
	Capsule->SetupAttachment(GetRootComponent());
	Capsule->SetCollisionResponseToAllChannels(ECollisionResponse::ECR_Ignore);
	Capsule->SetCollisionResponseToChannel(ECollisionChannel::ECC_Pawn, ECollisionResponse::ECR_Block);
}

void ABreakableActor::BeginPlay()
{
	Super::BeginPlay();
	
}

void ABreakableActor::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

}

void ABreakableActor::GetHit_Implementation(const FVector& ImpactPoint, AActor* Hitter)
{
	UWorld* World = GetWorld();
	if (World && TreasureClasses.Num() > 0)
	{
		if (bBroken) return;
		bBroken = true;

		if (GeometryCollection)
		{
			GeometryCollection->WakeAllRigidBodies();   // ① 唤醒（对应弹幕的休眠问题）

			// ② 直接施加应变（和碰撞产生的 strain 同一量纲，所以"能摔碎就一定能打碎"）
			GeometryCollection->ApplyExternalStrain(0, ImpactPoint, 200.f, 2, 0.5f, 100000000.f);

			// ③ 想让碎片飞出去（Linear Force 对 GC 常失效，这个更靠得住）
			GeometryCollection->ApplyBreakingLinearVelocity(
				0, (GetActorLocation() - ImpactPoint).GetSafeNormal() * 3000.f);
		}

		FVector Location = GetActorLocation();
		Location.Z += 75.f;
		const int32 Selection = FMath::RandRange(0, TreasureClasses.Num() - 1);
		World->SpawnActor<ATreasure>(TreasureClasses[Selection], Location, GetActorRotation());
	}
}

