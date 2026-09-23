import SwiftUI
import AITrainerCore

struct CoachView: View {
    @EnvironmentObject private var store: AppStore
    @State private var showShorten = false
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Panel {
                        Label("Local coach", systemImage: "brain").font(.title2.bold())
                        Text("Structured decisions, not a connected chatbot. No language model receives your logs.")
                        if let plan = store.state.nextPlan {
                            Text("Your accepted plan contains \(plan.slots.count) exercises for your stated \(store.state.profile?.goal.lowercased() ?? "training") goal. Load changes require comparable logs and your acceptance.")
                        }
                    }
                    Panel {
                        Text("What should change next?").font(.headline)
                        Button("I have less time") { showShorten = true }
                        ForEach(store.state.nextPlan?.slots ?? []) { slot in
                            Button("Review \(store.name(slot.exerciseID))") { store.request(.progression(slot.id)) }
                        }
                    }
                    ForEach(store.state.recommendations.filter { $0.status == .proposed }) { RecommendationPanel(recommendation: $0).id($0.id) }
                    Panel {
                        Text("What the coach does not infer").font(.headline)
                        Text("Unknown effort is not a positive signal. An omitted set is not lost strength. Rejected advice does not become a dislike. Camera, sleep, meals, and research outputs do not drive P1 progression.")
                    }
                }.padding()
            }
            .scrollToNewProposal(store.state.recommendations, proxy: proxy)
        }
        .background(Color(uiColor: .systemGroupedBackground)).navigationTitle("Coach")
            .sheet(isPresented: $showShorten) { ShortenView() }
    }
}
