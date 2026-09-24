// Fill out your copyright notice in the Description page of Project Settings.


#include "HUD/SlashHud.h"
#include "HUD/SlashOverlay.h"

void ASlashHud::BeginPlay()
{
	UWorld* World = GetWorld();
	if (World)
	{
		APlayerController* Controller = World->GetFirstPlayerController();
		if (Controller && SlashOverlayClass)
		{
			SlashOverlay = CreateWidget<USlashOverlay>(Controller, SlashOverlayClass);
			SlashOverlay->AddToViewport();
		}
	}
}
