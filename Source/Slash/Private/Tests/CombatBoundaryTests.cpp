#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Engine/World.h"
#include "Character/SlashCharacter.h"
#include "Enemy/Enemy.h"
#include "Components/AttributeComponent.h"
#include "Interface/HitInterface.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCombatBoundaryTest, "Slash.Combat.DamageAndDeathBoundaries",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCombatBoundaryTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    if (!TestNotNull(TEXT("Test world"), World)) return false;

    auto CheckCharacter = [this](ABaseCharacter* Character)
    {
        if (!TestNotNull(TEXT("Character spawned"), Character)) return;
        UAttributeComponent* Attributes = Character->FindComponentByClass<UAttributeComponent>();
        if (!TestNotNull(TEXT("Attributes"), Attributes)) return;
        IHitInterface::Execute_GetHit(Character, FVector::ZeroVector, nullptr);
        TestFalse(TEXT("Null hitter does not kill a healthy character"), Character->ActorHasTag(TEXT("Dead")));
        UGameplayStatics::ApplyDamage(Character, 10.f, nullptr, nullptr, nullptr);
        TestTrue(TEXT("Null instigator damage updates health"), FMath::IsNearlyEqual(Attributes->GetHealthPercent(), .9f));
        UGameplayStatics::ApplyDamage(Character, 1000.f, nullptr, nullptr, nullptr);
        TestTrue(TEXT("ApplyDamage alone completes death"), Character->ActorHasTag(TEXT("Dead")));
        const float InitialLifeSpan = Character->GetLifeSpan();
        // Simulate a partly elapsed lifespan without depending on the editor frame's timer tick.
        if (InitialLifeSpan > .25f) Character->SetLifeSpan(InitialLifeSpan - .25f);
        const float LifeSpan = Character->GetLifeSpan();
        if (InitialLifeSpan > 0.f)
            TestTrue(TEXT("Death lifespan shortened before repeated hit"), LifeSpan < InitialLifeSpan);
        UGameplayStatics::ApplyDamage(Character, 10.f, nullptr, nullptr, nullptr);
        IHitInterface::Execute_GetHit(Character, FVector::ZeroVector, nullptr);
        TestEqual(TEXT("Repeated hit does not reset death lifespan"), Character->GetLifeSpan(), LifeSpan);
        for (const FName Name : {FName("AttackEnd"), FName("DodgeEnd"), FName("HitReactEnd"), FName("FinishEquipping")})
        {
            if (UFunction* Function = Character->FindFunction(Name)) Character->ProcessEvent(Function, nullptr);
        }
        TestTrue(TEXT("Late animation callbacks preserve death"), Character->ActorHasTag(TEXT("Dead")));
        if (ASlashCharacter* Player = Cast<ASlashCharacter>(Character))
        {
            TestEqual(TEXT("Player remains in dead action state"),
                Player->GetActionState(), EActionState::EAS_Dead);
        }
    };
    CheckCharacter(World->SpawnActor<AEnemy>());
    CheckCharacter(World->SpawnActor<ASlashCharacter>());

    ASlashCharacter* DodgingPlayer = World->SpawnActor<ASlashCharacter>();
    if (TestNotNull(TEXT("Dodging player"), DodgingPlayer))
    {
        FEnumProperty* State = FindFProperty<FEnumProperty>(ASlashCharacter::StaticClass(), TEXT("ActionState"));
        if (TestNotNull(TEXT("Player action state property"), State))
        {
            State->GetUnderlyingProperty()->SetIntPropertyValue(
                State->ContainerPtrToValuePtr<void>(DodgingPlayer), static_cast<uint64>(EActionState::EAS_Dodge));
            UGameplayStatics::ApplyDamage(DodgingPlayer, 1000.f, nullptr, nullptr, nullptr);
            IHitInterface::Execute_GetHit(DodgingPlayer, FVector::ZeroVector, nullptr);
            TestFalse(TEXT("Dodge survives lethal damage"), DodgingPlayer->ActorHasTag(TEXT("Dead")));
            TestEqual(TEXT("Dodge ignores hit reaction"), DodgingPlayer->GetActionState(), EActionState::EAS_Dodge);
            TestEqual(TEXT("Dodge preserves health"),
                DodgingPlayer->FindComponentByClass<UAttributeComponent>()->GetHealthPercent(), 1.f);
        }
    }

    UAttributeComponent* EmptyAttributes = NewObject<UAttributeComponent>();
    for (const FName Name : {FName("MaxHealth"), FName("MaxStamina")})
    {
        FFloatProperty* Property = FindFProperty<FFloatProperty>(UAttributeComponent::StaticClass(), Name);
        if (TestNotNull(TEXT("Maximum attribute property"), Property))
            Property->SetPropertyValue_InContainer(EmptyAttributes, 0.f);
    }
    TestEqual(TEXT("Zero maximum health is safe"), EmptyAttributes->GetHealthPercent(), 0.f);
    TestEqual(TEXT("Zero maximum stamina is safe"), EmptyAttributes->GetStaminaPercent(), 0.f);
    World->DestroyWorld(false);
    return true;
}
#endif
