# 查找表 — 头文件 / 关键词 → 文档

本文件由 `tools/gen_agent_index.py` 从各篇 front-matter 自动生成。**它不是给人通读的**，请用 grep 或 `tools/tm_docs` 精确命中。

## 按头文件查

拿到一个 `#include <tm_kit/...>` 想查文档时用这张表。

| 头文件 | 文档 |
|---|---|
| `AbstractHookFactoryComponent.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `AbstractIdentityCheckerComponent.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `AlertEnhancedLoggingComponent.hpp` | [tm_transport/05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md) |
| `AlertMessage.hpp` | [tm_transport/05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md) |
| `AppClassifier.hpp` | [tm_infra/00-overview.md](tm_infra/00-overview.md)、[tm_infra/01-app-types.md](tm_infra/01-app-types.md) |
| `AppRunnerUtils.hpp` | [tm_basic/00-overview.md](tm_basic/00-overview.md)、[tm_basic/10-app-runner-utils.md](tm_basic/10-app-runner-utils.md) |
| `AutoConnectionSubGraph.hpp` | [tm_infra/06-declarative-graph.md](tm_infra/06-declarative-graph.md) |
| `BasicWithTimeApp.hpp` | [tm_infra/00-overview.md](tm_infra/00-overview.md)、[tm_infra/01-app-types.md](tm_infra/01-app-types.md)、[tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md) |
| `ByteData.hpp` | [tm_basic/00-overview.md](tm_basic/00-overview.md)、[tm_basic/03-serialization.md](tm_basic/03-serialization.md) |
| `ByteDataHook.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `ChainBackedFacility.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `ChainDataImporterExporter.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `ChainPollingPolicy.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `ChainReader.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `ChainWriter.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `ChronoUtils.hpp` | [tm_infra/07-time-and-data.md](tm_infra/07-time-and-data.md) |
| `Clock.hpp` | [tm_basic/01-clocks.md](tm_basic/01-clocks.md) |
| `ClockComponent.hpp` | [tm_basic/01-clocks.md](tm_basic/01-clocks.md) |
| `ClockImporter.hpp` | [tm_basic/01-clocks.md](tm_basic/01-clocks.md) |
| `ClockOnOrderFacility.hpp` | [tm_basic/01-clocks.md](tm_basic/01-clocks.md) |
| `CommonFlowUtils.hpp` | [tm_basic/00-overview.md](tm_basic/00-overview.md)、[tm_basic/05-common-flow-util.md](tm_basic/05-common-flow-util.md) |
| `ComplexInput.hpp` | [tm_transport/03-transports/json_rest.md](tm_transport/03-transports/json_rest.md) |
| `ConcatStructFieldInfo.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `ConnectionLocator.hpp` | [tm_transport/00-overview.md](tm_transport/00-overview.md) |
| `ConstStringType.hpp` | [tm_basic/06-value-types.md](tm_basic/06-value-types.md) |
| `ConstType.hpp` | [tm_basic/06-value-types.md](tm_basic/06-value-types.md) |
| `ConstValueType.hpp` | [tm_basic/06-value-types.md](tm_basic/06-value-types.md) |
| `ControllableNode.hpp` | [tm_infra/08-runners-and-control.md](tm_infra/08-runners-and-control.md) |
| `DBTableExporterFactory.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `DBTableImporterFactory.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `DataModel.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `DataStreamClientCombination.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `DataStreamEnvComponent.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `DataStreamInterface.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `DateHolder.hpp` | [tm_basic/06-value-types.md](tm_basic/06-value-types.md) |
| `DeclarativeGraph.hpp` | [tm_infra/06-declarative-graph.md](tm_infra/06-declarative-graph.md) |
| `DefaultUtilities.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `EmptyIdentityCheckerComponent.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `Environments.hpp` | [tm_infra/00-overview.md](tm_infra/00-overview.md)、[tm_infra/02-environments.md](tm_infra/02-environments.md) |
| `EtcdChain.hpp` | [tm_transport/04-shared-chains.md](tm_transport/04-shared-chains.md) |
| `EtcdHelper.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `EtcdLocalImporter.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `EtcdNamedValueStoreComponents.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `FixedPrecisionShortDecimal.hpp` | [tm_basic/06-value-types.md](tm_basic/06-value-types.md) |
| `FolderUsingPartialHistoryInformation.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `GeneralSubscriber.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `GenericLift.hpp` | [tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)、[tm_infra/04-facilities.md](tm_infra/04-facilities.md)、[tm_infra/06-declarative-graph.md](tm_infra/06-declarative-graph.md) |
| `GraphControlFacility.hpp` | [tm_basic/10-app-runner-utils.md](tm_basic/10-app-runner-utils.md) |
| `GrpcClientFacility.hpp` | [tm_transport/03-transports/grpc_interop.md](tm_transport/03-transports/grpc_interop.md) |
| `GrpcConnectionLocatorUtils.hpp` | [tm_transport/03-transports/grpc_interop.md](tm_transport/03-transports/grpc_interop.md) |
| `GrpcInteropComponent.hpp` | [tm_transport/03-transports/grpc_interop.md](tm_transport/03-transports/grpc_interop.md) |
| `GrpcServerFacility.hpp` | [tm_transport/03-transports/grpc_interop.md](tm_transport/03-transports/grpc_interop.md) |
| `GrpcServiceInfo.hpp` | [tm_transport/03-transports/grpc_interop.md](tm_transport/03-transports/grpc_interop.md) |
| `HeartbeatAndAlertComponent.hpp` | [tm_transport/05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md) |
| `HeartbeatMessage.hpp` | [tm_transport/05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md) |
| `HeartbeatMessageToRemoteFacilityCommand.hpp` | [tm_transport/05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md) |
| `InMemoryLockFreeChain.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `InMemorySharedChainCreator.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `InMemoryWithLockChain.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `JsonRESTClientFacility.hpp` | [tm_transport/03-transports/json_rest.md](tm_transport/03-transports/json_rest.md) |
| `JsonRESTComponent.hpp` | [tm_transport/03-transports/json_rest.md](tm_transport/03-transports/json_rest.md) |
| `JsonRESTFacilityWrapper.hpp` | [tm_transport/03-transports/json_rest.md](tm_transport/03-transports/json_rest.md) |
| `KleisliSequence.hpp` | [tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md) |
| `KleisliUtils.hpp` | [tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md) |
| `LockFreeInBoostSharedMemoryChain.hpp` | [tm_transport/04-shared-chains.md](tm_transport/04-shared-chains.md) |
| `LogLevel.hpp` | [tm_infra/08-runners-and-control.md](tm_infra/08-runners-and-control.md) |
| `LoggingComponentBase.hpp` | [tm_basic/04-logging.md](tm_basic/04-logging.md) |
| `MultiAppRunnerUtils.hpp` | [tm_basic/10-app-runner-utils.md](tm_basic/10-app-runner-utils.md) |
| `MultiTransportBroadcastListener.hpp` | [tm_transport/00-overview.md](tm_transport/00-overview.md)、[tm_transport/01-broadcast.md](tm_transport/01-broadcast.md) |
| `MultiTransportBroadcastListenerManagingUtils.hpp` | [tm_transport/01-broadcast.md](tm_transport/01-broadcast.md) |
| `MultiTransportBroadcastListenerManagingUtils_SynchronousRunner.hpp` | [tm_transport/01-broadcast.md](tm_transport/01-broadcast.md) |
| `MultiTransportBroadcastPublisherManagingUtils.hpp` | [tm_transport/01-broadcast.md](tm_transport/01-broadcast.md) |
| `MultiTransportFacilityWrapper.hpp` | [tm_transport/02-facilities.md](tm_transport/02-facilities.md) |
| `MultiTransportRemoteFacility.hpp` | [tm_transport/00-overview.md](tm_transport/00-overview.md)、[tm_transport/02-facilities.md](tm_transport/02-facilities.md) |
| `MultiTransportRemoteFacilityManagingUtils.hpp` | [tm_transport/02-facilities.md](tm_transport/02-facilities.md) |
| `MultiTransportTouchups.hpp` | [tm_transport/05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md) |
| `MulticastComponent.hpp` | [tm_transport/03-transports/multicast.md](tm_transport/03-transports/multicast.md) |
| `MulticastImporterExporter.hpp` | [tm_transport/03-transports/multicast.md](tm_transport/03-transports/multicast.md) |
| `NATSComponent.hpp` | [tm_transport/03-transports/nats.md](tm_transport/03-transports/nats.md) |
| `NATSImporterExporter.hpp` | [tm_transport/03-transports/nats.md](tm_transport/03-transports/nats.md) |
| `NATSOnOrderFacility.hpp` | [tm_transport/03-transports/nats.md](tm_transport/03-transports/nats.md) |
| `NNGComponent.hpp` | [tm_transport/03-transports/nng.md](tm_transport/03-transports/nng.md) |
| `NNGImporterExporter.hpp` | [tm_transport/03-transports/nng.md](tm_transport/03-transports/nng.md) |
| `NamedValueStoreConsumerCombination.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `NlohmannJsonInterop.hpp` | [tm_basic/03-serialization.md](tm_basic/03-serialization.md) |
| `ObservableNode.hpp` | [tm_infra/08-runners-and-control.md](tm_infra/08-runners-and-control.md) |
| `OnDemandReadonlyServer.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `OneShotChainWriter.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `PreloadAllReadonlyServer.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `ProtoInterop.hpp` | [tm_basic/03-serialization.md](tm_basic/03-serialization.md) |
| `RabbitMQComponent.hpp` | [tm_transport/03-transports/rabbitmq.md](tm_transport/03-transports/rabbitmq.md) |
| `RabbitMQImporterExporter.hpp` | [tm_transport/03-transports/rabbitmq.md](tm_transport/03-transports/rabbitmq.md) |
| `RabbitMQOnOrderFacility.hpp` | [tm_transport/03-transports/rabbitmq.md](tm_transport/03-transports/rabbitmq.md) |
| `RawString.hpp` | [tm_transport/03-transports/json_rest.md](tm_transport/03-transports/json_rest.md) |
| `RealTimeApp.hpp` | [tm_infra/00-overview.md](tm_infra/00-overview.md)、[tm_infra/01-app-types.md](tm_infra/01-app-types.md)、[tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)、[tm_infra/04-facilities.md](tm_infra/04-facilities.md) |
| `RealTimeApp_ConnectN_Piece.hpp` | [tm_infra/09-generated-pieces.md](tm_infra/09-generated-pieces.md) |
| `RealTimeApp_EnhancedMaybeN_Piece.hpp` | [tm_infra/09-generated-pieces.md](tm_infra/09-generated-pieces.md) |
| `RealTimeApp_Merge_Piece.hpp` | [tm_infra/09-generated-pieces.md](tm_infra/09-generated-pieces.md) |
| `RealTimeApp_PureN_Piece.hpp` | [tm_infra/09-generated-pieces.md](tm_infra/09-generated-pieces.md) |
| `RealTimeApp_VariantSink_Piece.hpp` | [tm_infra/09-generated-pieces.md](tm_infra/09-generated-pieces.md) |
| `RedisChain.hpp` | [tm_transport/04-shared-chains.md](tm_transport/04-shared-chains.md) |
| `RedisComponent.hpp` | [tm_transport/03-transports/redis.md](tm_transport/03-transports/redis.md) |
| `RedisImporterExporter.hpp` | [tm_transport/03-transports/redis.md](tm_transport/03-transports/redis.md) |
| `RedisOnOrderFacility.hpp` | [tm_transport/03-transports/redis.md](tm_transport/03-transports/redis.md) |
| `RemoteTransactionSubscriberManagingUtils.hpp` | [tm_transport/02-facilities.md](tm_transport/02-facilities.md) |
| `SelfContainedChainModifier.hpp` | [tm_basic/08-shared-chain.md](tm_basic/08-shared-chain.md) |
| `SerializationHelperMacros.hpp` | [tm_basic/00-overview.md](tm_basic/00-overview.md)、[tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `SharedChainCreator.hpp` | [tm_transport/04-shared-chains.md](tm_transport/04-shared-chains.md) |
| `SharedMemoryBroadcastComponent.hpp` | [tm_transport/03-transports/shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md) |
| `SharedMemoryBroadcastImporterExporter.hpp` | [tm_transport/03-transports/shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md) |
| `SignatureAndVerifyHookFactoryComponents.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `SignatureBasedIdentityCheckerComponent.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `SignatureHelper.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `SimpleIdentityCheckerComponent.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `SingleLayerWrapper.hpp` | [tm_basic/06-value-types.md](tm_basic/06-value-types.md) |
| `SinglePassIterationApp.hpp` | [tm_infra/00-overview.md](tm_infra/00-overview.md)、[tm_infra/01-app-types.md](tm_infra/01-app-types.md)、[tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md) |
| `SingleTableAsCollectionTransactionServer.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `SingleTablePerItemTransactionServer.hpp` | [tm_transport/07-kv-store-components.md](tm_transport/07-kv-store-components.md) |
| `SinglecastComponent.hpp` | [tm_transport/03-transports/singlecast.md](tm_transport/03-transports/singlecast.md) |
| `SinglecastImporterExporter.hpp` | [tm_transport/03-transports/singlecast.md](tm_transport/03-transports/singlecast.md) |
| `SocketRPCComponent.hpp` | [tm_transport/03-transports/socket_rpc.md](tm_transport/03-transports/socket_rpc.md) |
| `SocketRPCOnOrderFacility.hpp` | [tm_transport/03-transports/socket_rpc.md](tm_transport/03-transports/socket_rpc.md) |
| `SpdLoggingComponent.hpp` | [tm_basic/04-logging.md](tm_basic/04-logging.md) |
| `StructFieldFlattenedInfo.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `StructFieldInfoBasedCopy.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `StructFieldInfoBasedCsvUtils.hpp` | [tm_basic/07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md) |
| `StructFieldInfoBasedDynamicView.hpp` | [tm_basic/07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md) |
| `StructFieldInfoBasedFlatPackUtils.hpp` | [tm_basic/07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md) |
| `StructFieldInfoBasedHdf5Utils.hpp` | [tm_basic/07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md) |
| `StructFieldInfoHelper.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `StructFieldInfoHelper_NamedField.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `StructFieldInfoHelper_Tuple.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `StructFieldInfoUtils.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `StructFieldInfoWithMaskingFilter.hpp` | [tm_basic/02-struct-field-info.md](tm_basic/02-struct-field-info.md) |
| `SynchronousRunner.hpp` | [tm_infra/08-runners-and-control.md](tm_infra/08-runners-and-control.md) |
| `SyntheticMultiTransportFacility.hpp` | [tm_transport/02-facilities.md](tm_transport/02-facilities.md) |
| `TLSConfigurationComponent.hpp` | [tm_transport/06-security.md](tm_transport/06-security.md) |
| `TerminationController.hpp` | [tm_infra/08-runners-and-control.md](tm_infra/08-runners-and-control.md) |
| `TopDownSinglePassIterationApp.hpp` | [tm_infra/00-overview.md](tm_infra/00-overview.md)、[tm_infra/01-app-types.md](tm_infra/01-app-types.md)、[tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)、[tm_infra/04-facilities.md](tm_infra/04-facilities.md) |
| `TransactionDataStore.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `TransactionDeltaMerger.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `TransactionEnvComponent.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `TransactionFacility.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `TransactionInterface.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `TransactionLogicCombination.hpp` | [tm_basic/09-transaction.md](tm_basic/09-transaction.md) |
| `TrivialBoostLoggingComponent.hpp` | [tm_basic/04-logging.md](tm_basic/04-logging.md) |
| `TupleVariantHelper.hpp` | [tm_infra/07-time-and-data.md](tm_infra/07-time-and-data.md) |
| `VersionedData.hpp` | [tm_infra/07-time-and-data.md](tm_infra/07-time-and-data.md) |
| `VoidStruct.hpp` | [tm_basic/06-value-types.md](tm_basic/06-value-types.md) |
| `WebSocketClientFacility.hpp` | [tm_transport/03-transports/websocket.md](tm_transport/03-transports/websocket.md) |
| `WebSocketComponent.hpp` | [tm_transport/03-transports/websocket.md](tm_transport/03-transports/websocket.md) |
| `WebSocketImporterExporter.hpp` | [tm_transport/03-transports/websocket.md](tm_transport/03-transports/websocket.md) |
| `WebSocketLazyImporter.hpp` | [tm_transport/03-transports/websocket.md](tm_transport/03-transports/websocket.md) |
| `WebSocketServerFacility.hpp` | [tm_transport/03-transports/websocket.md](tm_transport/03-transports/websocket.md) |
| `WithTimeData.hpp` | [tm_infra/00-overview.md](tm_infra/00-overview.md)、[tm_infra/03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)、[tm_infra/04-facilities.md](tm_infra/04-facilities.md)、[tm_infra/05-app-runner.md](tm_infra/05-app-runner.md)、[tm_infra/07-time-and-data.md](tm_infra/07-time-and-data.md) |
| `WithTimeData_ConnectN_ClassPiece.hpp` | [tm_infra/05-app-runner.md](tm_infra/05-app-runner.md)、[tm_infra/09-generated-pieces.md](tm_infra/09-generated-pieces.md) |
| `WithTimeData_ConnectN_Piece.hpp` | [tm_infra/05-app-runner.md](tm_infra/05-app-runner.md) |
| `WithTimeData_VariantSink_ClassPiece.hpp` | [tm_infra/05-app-runner.md](tm_infra/05-app-runner.md)、[tm_infra/09-generated-pieces.md](tm_infra/09-generated-pieces.md) |
| `WithTimeData_VariantSink_Piece.hpp` | [tm_infra/05-app-runner.md](tm_infra/05-app-runner.md) |
| `ZeroMQComponent.hpp` | [tm_transport/03-transports/zeromq.md](tm_transport/03-transports/zeromq.md) |
| `ZeroMQImporterExporter.hpp` | [tm_transport/03-transports/zeromq.md](tm_transport/03-transports/zeromq.md) |

## 关键词索引

`tools/tm_docs find <关键词>` 的等价物。命中多篇时按篇名相关性排序。

- **.pc 修补** — [BUILD.md](BUILD.md)
- **action** — [00-overview.md](tm_infra/00-overview.md)
- **actionAsSink_2_0** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **ActionCore** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **addBroadcastChannel** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **addExtraHeartbeatHandler** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **addFacilityChannel** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **addTouchup** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **AlertEnhancedLoggingComponent** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **AlertMessage** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **AllChainComponents** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **AllNetworkTransportComponents** — [00-overview.md](tm_transport/00-overview.md)
- **amq.topic** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **AMQP** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **AnyIter** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **app runner** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **AppClassifier** — [01-app-types.md](tm_infra/01-app-types.md)
- **AppRunner** — [05-app-runner.md](tm_infra/05-app-runner.md)、[00-overview.md](tm_infra/00-overview.md)
- **AppRunnerUtilComponents** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **AppRunnerUtils** — [00-overview.md](tm_basic/00-overview.md)
- **AppSpecificMutex** — [01-app-types.md](tm_infra/01-app-types.md)
- **arity** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **attachHeartbeatAndAlertComponent** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **auth_token** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **auto_delete** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **AutoConnectionSubGraph** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **backtest** — [01-app-types.md](tm_infra/01-app-types.md)
- **basicDataStreamClientCombination** — [09-transaction.md](tm_basic/09-transaction.md)
- **BasicWithTimeApp** — [01-app-types.md](tm_infra/01-app-types.md)
- **BasicWithTimeAppChainCreator** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **binary** — [websocket.md](tm_transport/03-transports/websocket.md)
- **Boost.Asio** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **Boost.Interprocess** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **Boost.Preprocessor** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **BOOST_ROOT** — [BUILD.md](BUILD.md)
- **broadcast** — [00-overview.md](tm_transport/00-overview.md)
- **bufferingNode** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **build.sh** — [BUILD.md](BUILD.md)
- **BUILD_TYPE** — [BUILD.md](BUILD.md)
- **bunchedImporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **bunchWith** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **bunchWithProcessing** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **busyLoop** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **ByteData** — [03-serialization.md](tm_basic/03-serialization.md)
- **ByteDataHook** — [06-security.md](tm_transport/06-security.md)
- **ByteDataHookPair** — [02-facilities.md](tm_transport/02-facilities.md)、[06-security.md](tm_transport/06-security.md)
- **ByteDataView** — [03-serialization.md](tm_basic/03-serialization.md)
- **ByteDataWithID** — [03-serialization.md](tm_basic/03-serialization.md)、[socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **ByteDataWithTopic** — [03-serialization.md](tm_basic/03-serialization.md)
- **C# 绑定** — [00-overview.md](tm_infra/00-overview.md)
- **C++20** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **ca_cert** — [nats.md](tm_transport/03-transports/nats.md)、[redis.md](tm_transport/03-transports/redis.md)
- **CanBeActualTimeClock** — [01-clocks.md](tm_basic/01-clocks.md)
- **CBOR** — [03-serialization.md](tm_basic/03-serialization.md)
- **ChainBackedFacility** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **ChainDataImporterExporter** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **ChainItemFolder** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **ChainPollingPolicy** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **ChainReader** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **ChainWriter** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **ChainWritingStatus** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **channel spec** — [00-overview.md](tm_transport/00-overview.md)
- **CheckTimeComponent** — [02-environments.md](tm_infra/02-environments.md)、[07-time-and-data.md](tm_infra/07-time-and-data.md)
- **ChronoUtils** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **ClassPiece** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **client_cert** — [nats.md](tm_transport/03-transports/nats.md)、[redis.md](tm_transport/03-transports/redis.md)
- **client_key** — [nats.md](tm_transport/03-transports/nats.md)、[redis.md](tm_transport/03-transports/redis.md)
- **ClientSideSignatureBasedIdentityAttacherComponent** — [06-security.md](tm_transport/06-security.md)
- **ClientSideSimpleIdentityAttacherComponent** — [06-security.md](tm_transport/06-security.md)
- **ClockComponent** — [01-clocks.md](tm_basic/01-clocks.md)
- **ClockImporter** — [01-clocks.md](tm_basic/01-clocks.md)
- **ClockOnOrderFacility** — [01-clocks.md](tm_basic/01-clocks.md)
- **clone** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **collectAndPassDownOnRight** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **CommonFlowUtilComponents** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **CommonFlowUtils** — [00-overview.md](tm_basic/00-overview.md)
- **complex_key_value_store_components** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **ComplexInput** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **complexMovingTimeWindowActionKleisli** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **component** — [02-environments.md](tm_infra/02-environments.md)
- **compose** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **composeByteDataHookPair** — [06-security.md](tm_transport/06-security.md)
- **connect** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **connect_2_0** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **connectAny** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **connectAnySinkToAllImporters** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **ConnectionLocator** — [00-overview.md](tm_transport/00-overview.md)
- **connectSourceoidToAllSinks** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **connectSourceoidToAllUnusedSinks** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **connectSourceToAllSinks** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **connectSourceToAllUnusedSinks** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **connectTypedSinkToAllImporters** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **connectTypedSinkToAllNodes** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **ConstChecker** — [09-transaction.md](tm_basic/09-transaction.md)
- **constFirstPushImporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **ConstStringType** — [06-value-types.md](tm_basic/06-value-types.md)
- **ConstType** — [06-value-types.md](tm_basic/06-value-types.md)
- **ConstValueHolderComponent** — [02-environments.md](tm_infra/02-environments.md)
- **ConstValueType** — [06-value-types.md](tm_basic/06-value-types.md)
- **continuationAction** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **ConvertibleWithString** — [06-value-types.md](tm_basic/06-value-types.md)
- **convertIntoTuple2FacilitioidByDiscardingExtraValue** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **cppzmq** — [zeromq.md](tm_transport/03-transports/zeromq.md)
- **createOneShotTimer** — [01-clocks.md](tm_basic/01-clocks.md)
- **createRecurringTimer** — [01-clocks.md](tm_basic/01-clocks.md)
- **CSV** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **curlpp** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **curtailedAction** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **data-flow graph** — [00-overview.md](tm_infra/00-overview.md)
- **dataPrefix** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **dataStreamClientCombination** — [09-transaction.md](tm_basic/09-transaction.md)
- **DataStreamEnvComponent** — [09-transaction.md](tm_basic/09-transaction.md)
- **DataStreamInterface** — [09-transaction.md](tm_basic/09-transaction.md)
- **DateHolder** — [06-value-types.md](tm_basic/06-value-types.md)
- **db_table_importer_exporter** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **DBTableExporterFactory** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **DBTableImporterFactory** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **DeclarativeGraph** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **DeclarativeGraphChain** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **delayedImporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **delayer** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **DelaySimulator** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **DeleteAction** — [09-transaction.md](tm_basic/09-transaction.md)
- **detectCycle** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **DirectlySerializableChecker** — [03-serialization.md](tm_basic/03-serialization.md)
- **dispatchOneByOne** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **dispatchTupleAction** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **duplicateInput** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **durable** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **dynamicConnect** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **DynamicConstView** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **dynamicPlaceOrder** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **DynamicView** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **empty_clock** — [01-clocks.md](tm_basic/01-clocks.md)
- **EmptyEnvironment** — [02-environments.md](tm_infra/02-environments.md)
- **EncDecWithFieldNames** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **EncodableThroughMultipleProxies** — [06-value-types.md](tm_basic/06-value-types.md)
- **enhanced** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **enhancedMaybe2** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **envelop** — [multicast.md](tm_transport/03-transports/multicast.md)、[singlecast.md](tm_transport/03-transports/singlecast.md)
- **Environment** — [02-environments.md](tm_infra/02-environments.md)
- **EtcdChain** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **EtcdChainComponent** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **EtcdHelper** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **EtcdLocalImporter** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **EtcdNamedValueStoreComponents** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **exchange** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **expediter** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **exporter** — [00-overview.md](tm_infra/00-overview.md)、[03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **FacilitioidConnector** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)、[04-facilities.md](tm_infra/04-facilities.md)、[05-app-runner.md](tm_infra/05-app-runner.md)
- **facility** — [04-facilities.md](tm_infra/04-facilities.md)
- **FacilityWrapper** — [04-facilities.md](tm_infra/04-facilities.md)
- **facilityWrapper** — [02-facilities.md](tm_transport/02-facilities.md)
- **facilityWrapperWithProtocol** — [02-facilities.md](tm_transport/02-facilities.md)
- **fanOut** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **fetchFirstUpdateAndDisconnect** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **FIELD_NAMES** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **FIELD_OFFSETS** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **FieldOperationThroughAny** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **filterOnOptional** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **final flag** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **finalFlag** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **finalize** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **finalizeEnvironment** — [02-environments.md](tm_infra/02-environments.md)
- **FireOnceOnly** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **FixedPrecisionShortDecimal** — [06-value-types.md](tm_basic/06-value-types.md)
- **FlagExitControlComponent** — [02-environments.md](tm_infra/02-environments.md)
- **FlatPack** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **foldAndPassDownOnRight** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **FolderUsingPartialHistoryInformation** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **fromAbstractOnOrderFacility** — [04-facilities.md](tm_infra/04-facilities.md)
- **FullUpdate** — [09-transaction.md](tm_basic/09-transaction.md)
- **GeneralSubscriber** — [09-transaction.md](tm_basic/09-transaction.md)
- **GeneralSubscriberTypes** — [09-transaction.md](tm_basic/09-transaction.md)
- **GenericComponentLiftAndRegistration** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **GenericLift** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **getFieldIndex** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **glob 通配** — [redis.md](tm_transport/03-transports/redis.md)
- **graphControlFacility** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **GraphControlFacilityInput** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **groupByLookAhead** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **GroupedVersionedData** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **grpc_interop** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **GrpcClientFacilityFactory** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **GrpcInteropComponent** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **GrpcSerializationHelper** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **GrpcServerFacilityWrapper** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **GrpcServiceInfo** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **HasStructFieldInfo** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **HDF5** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **headKey** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **HeartbeatAndAlertComponent** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **HeartbeatAndAlertComponentTouchup** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **HeartbeatAndAlertComponentTouchupParameters** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **HeartbeatDirectedListenerTouchup** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **HeartbeatDirectedListenerTouchupSpec** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **HeartbeatMessage** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **HiddenTimeDependencyComponent** — [02-environments.md](tm_infra/02-environments.md)
- **hiredis** — [redis.md](tm_transport/03-transports/redis.md)
- **HTTP** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **IControllableNode** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **idFunc** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **IGeneralSubscriber** — [09-transaction.md](tm_basic/09-transaction.md)
- **ignoreTopic** — [multicast.md](tm_transport/03-transports/multicast.md)、[singlecast.md](tm_transport/03-transports/singlecast.md)、[websocket.md](tm_transport/03-transports/websocket.md)
- **ImmediatelyTerminate** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **importer** — [00-overview.md](tm_infra/00-overview.md)、[03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **importWithTrigger** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **initializeHeartbeatAndAlertComponent** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **InMemoryLockFreeChain** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **InMemorySharedChainCreator** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **InMemoryWithLockChain** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **InsertAction** — [09-transaction.md](tm_basic/09-transaction.md)
- **INSTALL_PREFIX** — [BUILD.md](BUILD.md)
- **interface** — [multicast.md](tm_transport/03-transports/multicast.md)
- **IObservableNode** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **ipc** — [nng.md](tm_transport/03-transports/nng.md)
- **IProtoDecoder** — [03-serialization.md](tm_basic/03-serialization.md)
- **IsFixedPrecisionShortDecimal** — [06-value-types.md](tm_basic/06-value-types.md)
- **IsKey** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **IsKeyedData** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **IsRemainingFieldHandler** — [03-serialization.md](tm_basic/03-serialization.md)
- **IsStructFieldInfoBasedCsvCompatibleStruct** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **ixwebsocket** — [websocket.md](tm_transport/03-transports/websocket.md)
- **IXWebSocket** — [websocket.md](tm_transport/03-transports/websocket.md)
- **Json** — [03-serialization.md](tm_basic/03-serialization.md)
- **JSON** — [03-serialization.md](tm_basic/03-serialization.md)、[json_rest.md](tm_transport/03-transports/json_rest.md)
- **json_rest** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **JsonDecoder** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonEncoder** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonFieldMapping** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonRequiredField** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonRESTClientFacility** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **JsonRESTComponent** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **JsonRESTFacilityWrapper** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **JsonVariant** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonVariantAutoDetect** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonVariantAutoDetectTypeMark** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonVariantTypeMark** — [03-serialization.md](tm_basic/03-serialization.md)
- **JsonWrappable** — [03-serialization.md](tm_basic/03-serialization.md)
- **Key** — [04-facilities.md](tm_infra/04-facilities.md)、[07-time-and-data.md](tm_infra/07-time-and-data.md)
- **KeyedData** — [04-facilities.md](tm_infra/04-facilities.md)、[07-time-and-data.md](tm_infra/07-time-and-data.md)
- **keyedSynchronizer2** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **keyify** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)、[04-facilities.md](tm_infra/04-facilities.md)、[07-time-and-data.md](tm_infra/07-time-and-data.md)
- **keyifyThroughCounter** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **kleisli** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **KleisliSequence** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **KleisliUtils** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **lazyImporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **leftShift** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **libnats** — [nats.md](tm_transport/03-transports/nats.md)
- **librabbitmq** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **libsodium** — [06-security.md](tm_transport/06-security.md)
- **libzmq** — [zeromq.md](tm_transport/03-transports/zeromq.md)
- **lift** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **liftMaybe** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **liftMulti** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **LiftParameters** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **liftPure** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **liftPure2** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **liftPureOnOrderFacility** — [04-facilities.md](tm_infra/04-facilities.md)
- **ListenerTouchup** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **ListenerTouchupSpec** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **LocalOnOrderFacility** — [04-facilities.md](tm_infra/04-facilities.md)
- **LockFreeInBoostSharedMemoryChain** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **log** — [04-logging.md](tm_basic/04-logging.md)
- **LoggingComponentBase** — [04-logging.md](tm_basic/04-logging.md)
- **LogLevel** — [04-logging.md](tm_basic/04-logging.md)、[08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **markStateSharing** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **merge2** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **mergedImporter** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **meson** — [BUILD.md](BUILD.md)
- **mixin** — [02-environments.md](tm_infra/02-environments.md)
- **mTLS** — [06-security.md](tm_transport/06-security.md)
- **multi_transport_touchups** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **MultiAppRunnerUtilComponents** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **multicast** — [multicast.md](tm_transport/03-transports/multicast.md)
- **MulticastComponent** — [multicast.md](tm_transport/03-transports/multicast.md)
- **MulticastImporterExporter** — [multicast.md](tm_transport/03-transports/multicast.md)
- **MultiTransport** — [00-overview.md](tm_transport/00-overview.md)
- **MultiTransportBroadcastFirstUpdateQueryManagingUtils** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **MultiTransportBroadcastListener** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **MultiTransportBroadcastListenerManagingUtils** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **MultiTransportBroadcastListenerSpec** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **MultiTransportBroadcastPublisherManagingUtils** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **MultiTransportFacilityWrapper** — [02-facilities.md](tm_transport/02-facilities.md)
- **MultiTransportRemoteFacility** — [02-facilities.md](tm_transport/02-facilities.md)
- **MultiTransportRemoteFacilityDispatchStrategy** — [02-facilities.md](tm_transport/02-facilities.md)
- **MultiTransportRemoteFacilityManagingUtils** — [02-facilities.md](tm_transport/02-facilities.md)
- **named_value_store** — [09-transaction.md](tm_basic/09-transaction.md)
- **named_value_store_components** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **NamedValueStoreConsumerCombination** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **namespace/service/method** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **nanomsg-next-gen** — [nng.md](tm_transport/03-transports/nng.md)
- **NATS** — [nats.md](tm_transport/03-transports/nats.md)
- **nats.c** — [nats.md](tm_transport/03-transports/nats.md)
- **NATSComponent** — [nats.md](tm_transport/03-transports/nats.md)
- **NATSImporterExporter** — [nats.md](tm_transport/03-transports/nats.md)
- **NATSOnOrderFacility** — [nats.md](tm_transport/03-transports/nats.md)
- **ninja** — [BUILD.md](BUILD.md)
- **NINJA_JOBS** — [BUILD.md](BUILD.md)
- **nlohmann_json** — [03-serialization.md](tm_basic/03-serialization.md)
- **NNG** — [nng.md](tm_transport/03-transports/nng.md)
- **NNGComponent** — [nng.md](tm_transport/03-transports/nng.md)
- **NNGImporterExporter** — [nng.md](tm_transport/03-transports/nng.md)
- **nngpp** — [nng.md](tm_transport/03-transports/nng.md)
- **no_content_type** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **no_verify** — [json_rest.md](tm_transport/03-transports/json_rest.md)、[websocket.md](tm_transport/03-transports/websocket.md)
- **NoHiddenTimeDependencyComponent** — [02-environments.md](tm_infra/02-environments.md)
- **on-order facility** — [04-facilities.md](tm_infra/04-facilities.md)、[00-overview.md](tm_infra/00-overview.md)、[00-overview.md](tm_transport/00-overview.md)
- **OnDemandReadonlyServer** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **oneBroadcastListener** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **oneBroadcastListenerWithProtocol** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **oneBroadcastListenerWithTopic** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **oneBroadcastPublisher** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **oneBroadcastPublisherWithProtocol** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **oneByteDataBroadcastListener** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **oneByteDataBroadcastPublisher** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **OneDeltaUpdateItem** — [09-transaction.md](tm_basic/09-transaction.md)
- **OneFullUpdateItem** — [09-transaction.md](tm_basic/09-transaction.md)
- **OneShotChainWriter** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **OneUpdateItem** — [09-transaction.md](tm_basic/09-transaction.md)
- **OnOrderFacility** — [04-facilities.md](tm_infra/04-facilities.md)
- **OnOrderFacilityWithExternalEffects** — [04-facilities.md](tm_infra/04-facilities.md)
- **overview** — [00-overview.md](tm_basic/00-overview.md)
- **parallelArrow** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **parse_header** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **parseLocalTodayActualTime** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **passive** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **passThroughAction** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **persistent** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **pickOne** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **pickOneFromWrappedValue** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **Piece** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **pkg-config** — [BUILD.md](BUILD.md)
- **PKG_CONFIG_PATH** — [BUILD.md](BUILD.md)
- **placeOrderWithFacility** — [04-facilities.md](tm_infra/04-facilities.md)
- **PreloadAllReadonlyServer** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **PreserveInputRelativeOrder** — [01-clocks.md](tm_basic/01-clocks.md)、[01-app-types.md](tm_infra/01-app-types.md)
- **preserveLeft** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **preservePointer** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **preserveRight** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **ProducerN** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **PROTECT_TYPE** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **Proto** — [03-serialization.md](tm_basic/03-serialization.md)
- **proto** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **protobuf** — [03-serialization.md](tm_basic/03-serialization.md)、[grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **ProtobufStyleSerializableChecker** — [03-serialization.md](tm_basic/03-serialization.md)
- **ProtoDecoder** — [03-serialization.md](tm_basic/03-serialization.md)
- **ProtoEncoder** — [03-serialization.md](tm_basic/03-serialization.md)
- **ProtoInterop** — [03-serialization.md](tm_basic/03-serialization.md)
- **ProtoWrappable** — [03-serialization.md](tm_basic/03-serialization.md)
- **pub sub** — [nng.md](tm_transport/03-transports/nng.md)、[redis.md](tm_transport/03-transports/redis.md)、[zeromq.md](tm_transport/03-transports/zeromq.md)
- **PublisherTouchup** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **PublisherTouchupSpec** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **publishHeartbeat** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **pureExporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **pureFilter** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **RabbitMQ** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **RabbitMQComponent** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **RabbitMQImporterExporter** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **RabbitMQOnOrderFacility** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **RawString** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **read_simd** — [03-serialization.md](tm_basic/03-serialization.md)
- **read_simd_ondemand** — [03-serialization.md](tm_basic/03-serialization.md)
- **real_time_clock** — [01-clocks.md](tm_basic/01-clocks.md)
- **RealTimeApp** — [01-app-types.md](tm_infra/01-app-types.md)
- **Redis** — [redis.md](tm_transport/03-transports/redis.md)
- **redis_ssl** — [redis.md](tm_transport/03-transports/redis.md)
- **RedisChain** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **RedisChainComponent** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **RedisComponent** — [redis.md](tm_transport/03-transports/redis.md)
- **RedisImporterExporter** — [redis.md](tm_transport/03-transports/redis.md)
- **RedisOnOrderFacility** — [redis.md](tm_transport/03-transports/redis.md)
- **REFERENCE_NAME** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **registerAction** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **registerExporter** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **registerImporter** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **RemainingFieldHandler** — [03-serialization.md](tm_basic/03-serialization.md)
- **RequestDecision** — [09-transaction.md](tm_basic/09-transaction.md)
- **resolveTime** — [01-clocks.md](tm_basic/01-clocks.md)、[07-time-and-data.md](tm_infra/07-time-and-data.md)
- **REST** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **rightShift** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **RPC** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)、[04-facilities.md](tm_infra/04-facilities.md)、[02-facilities.md](tm_transport/02-facilities.md)、[grpc_interop.md](tm_transport/03-transports/grpc_interop.md)、[nats.md](tm_transport/03-transports/nats.md)、[redis.md](tm_transport/03-transports/redis.md)
- **RunCBORDeserializer** — [03-serialization.md](tm_basic/03-serialization.md)
- **RunCBORSerializer** — [03-serialization.md](tm_basic/03-serialization.md)
- **RunDeserializer** — [03-serialization.md](tm_basic/03-serialization.md)
- **RunForever** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **RunSerializer** — [03-serialization.md](tm_basic/03-serialization.md)
- **SelfContainedChainModifier** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **sendAlert** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **sendCustomMessage** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **ServerSideSimpleIdentityCheckerComponent** — [06-security.md](tm_transport/06-security.md)
- **setDocRoot** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **setLogFilePrefix** — [04-logging.md](tm_basic/04-logging.md)
- **setMaxOutputConnectivity** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **setStatus** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **setupBroadcastListeners** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **setupBroadcastListenersWithTopic** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **setupBroadcastListenerThroughHeartbeat** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **setupExitTimer** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **setupOneDistinguishedRemoteFacility** — [02-facilities.md](tm_transport/02-facilities.md)
- **setupOneNonDistinguishedRemoteFacility** — [02-facilities.md](tm_transport/02-facilities.md)
- **setupSimpleRemoteFacilitioid** — [02-facilities.md](tm_transport/02-facilities.md)
- **setupSimpleRemoteFacilitioidByHeartbeat** — [02-facilities.md](tm_transport/02-facilities.md)
- **setupSimpleRemoteFacility** — [02-facilities.md](tm_transport/02-facilities.md)
- **setupTwoStepRemoteFacility** — [02-facilities.md](tm_transport/02-facilities.md)
- **setupVIEFacilitySelfLoopAndWait** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **shareBetweenDownstream** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **shared_memory_broadcast** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **SharedChainCreator** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **SharedChainProtocol** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **SharedMemoryBroadcastComponent** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **SharedMemoryBroadcastImporterExporter** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **SharedMemoryChainComponent** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **shiftedImporter** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **SignatureBasedIdentityCheckerComponent** — [06-security.md](tm_transport/06-security.md)
- **SignatureHelper** — [06-security.md](tm_transport/06-security.md)
- **SignatureHookFactoryComponent** — [06-security.md](tm_transport/06-security.md)
- **simdjson** — [03-serialization.md](tm_basic/03-serialization.md)
- **simple_shared_chain** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **simpleFinalizer** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **simpleImporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **simpleMovingTimeWindowKleisli** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **SimpleRemoteFacilitySpecByHeartbeat** — [02-facilities.md](tm_transport/02-facilities.md)
- **simulatedFacility** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **single_pass_iteration_clock** — [01-clocks.md](tm_basic/01-clocks.md)
- **single_rpc** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **singlecast** — [singlecast.md](tm_transport/03-transports/singlecast.md)
- **SinglecastComponent** — [singlecast.md](tm_transport/03-transports/singlecast.md)
- **SinglecastImporterExporter** — [singlecast.md](tm_transport/03-transports/singlecast.md)
- **SingleLayerWrapper** — [06-value-types.md](tm_basic/06-value-types.md)
- **SingleLayerWrapperWithID** — [06-value-types.md](tm_basic/06-value-types.md)
- **SingleLayerWrapperWithTypeMark** — [06-value-types.md](tm_basic/06-value-types.md)
- **SinglePassIterationApp** — [01-app-types.md](tm_infra/01-app-types.md)
- **SingleTableAsCollectionTransactionServer** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **SingleTablePerItemTransactionServer** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **Sink** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **Sinkoid** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **size** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **snapshotOnRight** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **SOCI** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **socket_rpc** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **SocketRPCComponent** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **SocketRPCOnOrderFacility** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **Source** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **Sourceoid** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **spdlog** — [04-logging.md](tm_basic/04-logging.md)
- **SpdLoggingComponent** — [04-logging.md](tm_basic/04-logging.md)
- **std::tuple** — [00-overview.md](tm_infra/00-overview.md)
- **std::variant** — [00-overview.md](tm_infra/00-overview.md)
- **StructFieldInfo** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **StructFieldInfoBasedCsvExporterFactory** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoBasedCsvImporterFactory** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoBasedCsvInputOption** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoBasedHdf5Utils** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoBasedSimpleCsvInput** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoBasedSimpleCsvOutput** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoBasedSimpleFlatPackInput** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoBasedSimpleFlatPackOutput** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **StructFieldInfoUtils_SociHelper** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **StructFieldOffsetInfo** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **StructFieldTypeInfo** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **SuggestThreaded** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **synchronizer2** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **SynchronousRunner** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **SyntheticMultiTransportFacility** — [02-facilities.md](tm_transport/02-facilities.md)
- **tag** — [04-facilities.md](tm_infra/04-facilities.md)
- **tcp** — [nng.md](tm_transport/03-transports/nng.md)
- **TerminateAfterDuration** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **TerminateAtTimePoint** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **TerminationController** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **terminationController** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **TimeChecker** — [07-time-and-data.md](tm_infra/07-time-and-data.md)、[09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **TimeComponentEnhancedWithBoostTrivialLogging** — [01-clocks.md](tm_basic/01-clocks.md)、[04-logging.md](tm_basic/04-logging.md)
- **TimeComponentEnhancedWithSpdLogging** — [01-clocks.md](tm_basic/01-clocks.md)、[04-logging.md](tm_basic/04-logging.md)
- **TimedAppData** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **TimedAppModelContinuation** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **TimedAppModelKleisli** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **TimedAppMultiData** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **TimedDataWithEnvironment** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **TimePoint** — [01-clocks.md](tm_basic/01-clocks.md)
- **TLS** — [06-security.md](tm_transport/06-security.md)
- **TLSClientConfigurationComponent** — [06-security.md](tm_transport/06-security.md)
- **TLSClientInfo** — [06-security.md](tm_transport/06-security.md)
- **TLSServerConfigurationComponent** — [06-security.md](tm_transport/06-security.md)
- **TLSServerInfo** — [06-security.md](tm_transport/06-security.md)
- **tm_basic** — [00-overview.md](tm_basic/00-overview.md)
- **TM_BASIC_CBOR_CAPABLE_EMPTY_STRUCT** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **TM_BASIC_CBOR_CAPABLE_ENUM_AS_STRING** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **TM_BASIC_CBOR_CAPABLE_STRUCT** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE_NO_FIELD_NAMES** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **tm_infra** — [00-overview.md](tm_infra/00-overview.md)
- **TM_SERIALIZATION_HELPER_COMMA_START_POS** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **tm_transport** — [00-overview.md](tm_transport/00-overview.md)
- **top_down_single_pass_iteration_clock** — [01-clocks.md](tm_basic/01-clocks.md)
- **TopDownSinglePassIterationApp** — [01-app-types.md](tm_infra/01-app-types.md)
- **topic 通配** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **topicDescription** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **touchup** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **TransactionDataStore** — [09-transaction.md](tm_basic/09-transaction.md)
- **TransactionDeltaMerger** — [09-transaction.md](tm_basic/09-transaction.md)
- **TransactionEnvComponent** — [09-transaction.md](tm_basic/09-transaction.md)
- **TransactionInterface** — [09-transaction.md](tm_basic/09-transaction.md)
- **transactionLogicCombination** — [09-transaction.md](tm_basic/09-transaction.md)
- **TransactionProcessor** — [09-transaction.md](tm_basic/09-transaction.md)
- **TransactionResponse** — [09-transaction.md](tm_basic/09-transaction.md)
- **triggerImporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **TrivialBoostLoggingComponent** — [04-logging.md](tm_basic/04-logging.md)
- **TrivialExitControlComponent** — [02-environments.md](tm_infra/02-environments.md)
- **trivialExporter** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **TriviallyMerge** — [09-transaction.md](tm_basic/09-transaction.md)
- **TriviallyProcess** — [09-transaction.md](tm_basic/09-transaction.md)
- **TupleVariantHelper** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **TypeScript 绑定** — [00-overview.md](tm_infra/00-overview.md)
- **UDP 单播** — [singlecast.md](tm_transport/03-transports/singlecast.md)
- **UDP 组播** — [multicast.md](tm_transport/03-transports/multicast.md)
- **Update** — [09-transaction.md](tm_basic/09-transaction.md)
- **UpdateAction** — [09-transaction.md](tm_basic/09-transaction.md)
- **use_curlpp** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **use_keep_alive_client** — [json_rest.md](tm_transport/03-transports/json_rest.md)
- **useIXWebSocket** — [websocket.md](tm_transport/03-transports/websocket.md)
- **useNotification** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **UserToWireHook** — [06-security.md](tm_transport/06-security.md)
- **VariantSink** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **vcpkg** — [BUILD.md](BUILD.md)
- **VCPKG_ROOT** — [BUILD.md](BUILD.md)
- **VerifyHookFactoryComponent** — [06-security.md](tm_transport/06-security.md)
- **VersionChecker** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **VersionedData** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **vhost** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **VIEFacility** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **VIEOnOrderFacility** — [04-facilities.md](tm_infra/04-facilities.md)
- **VoidStruct** — [06-value-types.md](tm_basic/06-value-types.md)
- **websocket** — [websocket.md](tm_transport/03-transports/websocket.md)
- **WebSocketClientFacility** — [websocket.md](tm_transport/03-transports/websocket.md)
- **WebSocketComponent** — [websocket.md](tm_transport/03-transports/websocket.md)
- **WebSocketImporterExporter** — [websocket.md](tm_transport/03-transports/websocket.md)
- **WebSocketOnOrderFacility** — [websocket.md](tm_transport/03-transports/websocket.md)
- **WebSocketServerFacility** — [websocket.md](tm_transport/03-transports/websocket.md)
- **wholeHistoryFold** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **WireToUserHook** — [06-security.md](tm_transport/06-security.md)
- **WithStart** — [04-facilities.md](tm_infra/04-facilities.md)
- **WithTime** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **withtime_utils** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **wrapFacilitioidConnector** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **wrapFacilitioidConnectorBackOnly** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **wrapFacilitioidConnectorFrontOnly** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **wrappedOnOrderFacility** — [04-facilities.md](tm_infra/04-facilities.md)
- **wrapTuple2FacilitioidBySupplyingDefaultValue** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **wrapTuple2OnOrderFacilityBySupplyingDefaultValue** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **writeGraphVizDescription** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **ZeroMQ** — [zeromq.md](tm_transport/03-transports/zeromq.md)
- **ZeroMQComponent** — [zeromq.md](tm_transport/03-transports/zeromq.md)
- **ZeroMQImporterExporter** — [zeromq.md](tm_transport/03-transports/zeromq.md)
- **zoned_time** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **乐观锁** — [09-transaction.md](tm_basic/09-transaction.md)
- **事件溯源** — [08-shared-chain.md](tm_basic/08-shared-chain.md)、[04-shared-chains.md](tm_transport/04-shared-chains.md)
- **事务服务** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **交易日** — [06-value-types.md](tm_basic/06-value-types.md)
- **传输能力矩阵** — [00-overview.md](tm_transport/00-overview.md)
- **低延迟** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)、[zeromq.md](tm_transport/03-transports/zeromq.md)
- **信号类型** — [06-value-types.md](tm_basic/06-value-types.md)
- **信道标识** — [00-overview.md](tm_transport/00-overview.md)
- **停止控制** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **元数** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **共享内存** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **共享链** — [08-shared-chain.md](tm_basic/08-shared-chain.md)、[04-shared-chains.md](tm_transport/04-shared-chains.md)
- **分布式一致性** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **分布式事务** — [09-transaction.md](tm_basic/09-transaction.md)
- **前端** — [json_rest.md](tm_transport/03-transports/json_rest.md)、[websocket.md](tm_transport/03-transports/websocket.md)
- **加密** — [06-security.md](tm_transport/06-security.md)
- **动态视图** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **包装器** — [06-value-types.md](tm_basic/06-value-types.md)
- **单向** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **单次写入** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **双向** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)、[websocket.md](tm_transport/03-transports/websocket.md)
- **双向流** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **反射** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **发布** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **只读查询** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **同机进程间** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)
- **同步运行** — [08-runners-and-control.md](tm_infra/08-runners-and-control.md)
- **同网段** — [multicast.md](tm_transport/03-transports/multicast.md)
- **告警** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **回测** — [01-app-types.md](tm_infra/01-app-types.md)
- **固定精度** — [06-value-types.md](tm_basic/06-value-types.md)
- **图控制** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **图构建** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **均值** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **声明式** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **多传输抽象** — [00-overview.md](tm_transport/00-overview.md)
- **多图交错运行** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **头文件地图** — [00-overview.md](tm_infra/00-overview.md)
- **字段遍历** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **安装** — [BUILD.md](BUILD.md)
- **定点小数** — [06-value-types.md](tm_basic/06-value-types.md)
- **常量类型** — [06-value-types.md](tm_basic/06-value-types.md)
- **广播** — [01-broadcast.md](tm_transport/01-broadcast.md)、[00-overview.md](tm_transport/00-overview.md)
- **序列化** — [03-serialization.md](tm_basic/03-serialization.md)、[00-overview.md](tm_basic/00-overview.md)
- **序列化宏** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **心跳** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **成环** — [04-facilities.md](tm_infra/04-facilities.md)
- **执行模型** — [01-app-types.md](tm_infra/01-app-types.md)
- **批处理** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **批聚合** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **批量IO** — [07-csv-hdf5-flatpack.md](tm_basic/07-csv-hdf5-flatpack.md)
- **按单设施** — [04-facilities.md](tm_infra/04-facilities.md)
- **提升** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **数字后缀** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **数据库表** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)
- **数据流图** — [00-overview.md](tm_infra/00-overview.md)
- **数据订阅** — [09-transaction.md](tm_basic/09-transaction.md)
- **无 broker** — [multicast.md](tm_transport/03-transports/multicast.md)、[nng.md](tm_transport/03-transports/nng.md)、[singlecast.md](tm_transport/03-transports/singlecast.md)、[socket_rpc.md](tm_transport/03-transports/socket_rpc.md)、[zeromq.md](tm_transport/03-transports/zeromq.md)
- **日志** — [04-logging.md](tm_basic/04-logging.md)、[00-overview.md](tm_basic/00-overview.md)
- **日志组件** — [04-logging.md](tm_basic/04-logging.md)
- **日期** — [06-value-types.md](tm_basic/06-value-types.md)
- **时区** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **时序合并** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **时钟** — [01-clocks.md](tm_basic/01-clocks.md)、[00-overview.md](tm_basic/00-overview.md)
- **时间倒流** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **时间戳** — [07-time-and-data.md](tm_infra/07-time-and-data.md)
- **时间窗口** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **服务发现** — [01-broadcast.md](tm_transport/01-broadcast.md)、[05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **服务注册** — [02-facilities.md](tm_transport/02-facilities.md)
- **服务状态** — [05-heartbeat-and-alert.md](tm_transport/05-heartbeat-and-alert.md)
- **构建** — [BUILD.md](BUILD.md)
- **概览** — [00-overview.md](tm_basic/00-overview.md)
- **注册** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **浏览器** — [json_rest.md](tm_transport/03-transports/json_rest.md)、[websocket.md](tm_transport/03-transports/websocket.md)
- **消息队列** — [rabbitmq.md](tm_transport/03-transports/rabbitmq.md)
- **滑动窗口** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **滑窗** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **点对点** — [singlecast.md](tm_transport/03-transports/singlecast.md)
- **环境变量** — [BUILD.md](BUILD.md)
- **生成代码** — [09-generated-pieces.md](tm_infra/09-generated-pieces.md)
- **直连** — [nng.md](tm_transport/03-transports/nng.md)、[zeromq.md](tm_transport/03-transports/zeromq.md)
- **签名** — [06-security.md](tm_transport/06-security.md)
- **类型适配** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **线程模型** — [01-app-types.md](tm_infra/01-app-types.md)
- **组件** — [02-environments.md](tm_infra/02-environments.md)
- **组图** — [05-app-runner.md](tm_infra/05-app-runner.md)
- **编译** — [BUILD.md](BUILD.md)
- **编译期反射** — [02-struct-field-info.md](tm_basic/02-struct-field-info.md)
- **网卡** — [multicast.md](tm_transport/03-transports/multicast.md)
- **节点创建** — [03-nodes-and-lifting.md](tm_infra/03-nodes-and-lifting.md)
- **虚继承** — [02-environments.md](tm_infra/02-environments.md)
- **行情分发** — [multicast.md](tm_transport/03-transports/multicast.md)、[zeromq.md](tm_transport/03-transports/zeromq.md)
- **裸 TCP** — [socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **订阅** — [01-broadcast.md](tm_transport/01-broadcast.md)
- **请求响应** — [02-facilities.md](tm_transport/02-facilities.md)、[socket_rpc.md](tm_transport/03-transports/socket_rpc.md)
- **跨语言** — [grpc_interop.md](tm_transport/03-transports/grpc_interop.md)
- **身份校验** — [06-security.md](tm_transport/06-security.md)
- **轻量消息总线** — [nats.md](tm_transport/03-transports/nats.md)
- **远程设施** — [02-facilities.md](tm_transport/02-facilities.md)、[00-overview.md](tm_transport/00-overview.md)
- **连接** — [06-declarative-graph.md](tm_infra/06-declarative-graph.md)
- **退出计时器** — [10-app-runner-utils.md](tm_basic/10-app-runner-utils.md)
- **通用流工具** — [05-common-flow-util.md](tm_basic/05-common-flow-util.md)
- **通配** — [nats.md](tm_transport/03-transports/nats.md)
- **链写入** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **链复制** — [04-shared-chains.md](tm_transport/04-shared-chains.md)
- **链接错误** — [BUILD.md](BUILD.md)
- **链读取** — [08-shared-chain.md](tm_basic/08-shared-chain.md)
- **键值存储** — [07-kv-store-components.md](tm_transport/07-kv-store-components.md)、[redis.md](tm_transport/03-transports/redis.md)
- **零拷贝** — [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md)

---

*重新生成：`python3 tools/gen_agent_index.py`*
